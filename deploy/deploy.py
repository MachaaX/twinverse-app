#!/usr/bin/env python3
"""Deploy a public repository's tested main commit; run by the EC2 systemd timer.

The controller/config are installed separately as root-owned files. Repository
tests and dependency installation run as an unprivileged build user without the
app's environment. App releases and mutable SQLite data have separate locations.
"""
import argparse
import fcntl
import json
import os
import re
import shutil
import sqlite3
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = Path('/opt/twinverse')
STATE = Path('/var/lib/twinverse-deploy')
BACKUPS = Path('/var/backups/twinverse')
DATABASE = Path('/var/lib/twinverse/twinverse.sqlite3')
CONFIG = Path('/etc/twinverse/deploy.json')
BUILD_USER = 'twinverse-build'


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def read_json(url):
    request = urllib.request.Request(url, headers={
        'Accept': 'application/vnd.github+json', 'User-Agent': 'TwinVerse-EC2-deployer',
        'X-GitHub-Api-Version': '2022-11-28'})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read(2_000_000))


def passed_ci(repository, branch, sha):
    query = urllib.parse.urlencode({'head_sha': sha, 'branch': branch, 'event': 'push', 'per_page': 20})
    data = read_json(f'https://api.github.com/repos/{repository}/actions/workflows/ci.yml/runs?{query}')
    runs = [item for item in data.get('workflow_runs', [])
            if item.get('head_sha') == sha and item.get('head_branch') == branch
            and item.get('event') == 'push']
    # A newer pending/failed rerun must not be hidden by an older successful run.
    latest = max(runs, key=lambda item: (item['id'], item.get('run_attempt', 1)), default={})
    return latest.get('status') == 'completed' and latest.get('conclusion') == 'success'


def switch_link(release):
    temporary = BASE / 'current.next'
    temporary.unlink(missing_ok=True)
    temporary.symlink_to(release)
    temporary.replace(BASE / 'current')


def healthy(sha):
    try:
        with urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3) as response:
            data = json.loads(response.read(4096))
        return data.get('status') == 'ok' and data.get('release') == sha
    except (OSError, ValueError):
        return False


def await_health(sha):
    for _ in range(30):
        if healthy(sha):
            return True
        time.sleep(1)
    return False


def backup_database():
    if not DATABASE.exists():
        return
    BACKUPS.mkdir(parents=True, exist_ok=True)
    path = BACKUPS / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.sqlite3')
    with sqlite3.connect(DATABASE, timeout=30) as source, sqlite3.connect(path) as target:
        source.backup(target)
    path.chmod(0o600)
    for old in sorted(BACKUPS.glob('*.sqlite3'))[:-10]:
        old.unlink()


def activate(release):
    current = BASE / 'current'
    previous = current.resolve() if current.is_symlink() else None
    backup_database()
    switch_link(release)
    try:
        run('systemctl', 'restart', 'twinverse.service')
        if not await_health(release.name):
            raise RuntimeError('New release did not pass its HTTP health check.')
    except Exception:
        if previous:
            switch_link(previous)
            run('systemctl', 'restart', 'twinverse.service')
            if not await_health(previous.name):
                raise RuntimeError('Rollback also failed its health check; inspect journalctl -u twinverse.') from None
            print('Rolled back to the previous healthy release: ' + previous.name, flush=True)
        else:
            current.unlink(missing_ok=True)
            run('systemctl', 'stop', 'twinverse.service')
        raise
    (STATE / 'last-success.json').write_text(json.dumps({
        'sha': release.name, 'previous': previous.name if previous else None,
        'deployed_at': datetime.now(timezone.utc).isoformat()}) + '\n')
    print('Deployed healthy release: ' + release.name, flush=True)
    # Keep recent releases and the rollback target without filling the EBS disk.
    releases = sorted((BASE/'releases').iterdir(), key=lambda path:path.stat().st_mtime, reverse=True)
    keep = {release, previous, *releases[:5]}
    for old in releases:
        if old not in keep and re.fullmatch(r'[0-9a-f]{40}', old.name) and (old/'.ready').is_file():
            shutil.rmtree(old)


def build_release(repository, sha):
    release = BASE / 'releases' / sha
    if (release / '.ready').is_file():
        return release
    if release.exists():
        current = BASE / 'current'
        if current.is_symlink() and current.resolve() == release:
            raise RuntimeError('The active release is incomplete; refusing to remove it.')
        shutil.rmtree(release)
    release.mkdir(parents=True)
    # Git archive only includes committed files; .env, local databases and keys
    # are never copied from a developer checkout to a release.
    archive = STATE / 'source.tar'
    with archive.open('wb') as output:
        run('git', '--git-dir=' + str(repository), 'archive', sha, stdout=output)
    run('tar', '-xf', str(archive), '-C', str(release), '--no-same-owner', '--no-same-permissions')
    archive.unlink()
    run('chown', '-R', BUILD_USER + ':' + BUILD_USER, str(release))
    environment = {'PATH': '/usr/local/bin:/usr/bin:/bin', 'HOME': '/var/lib/twinverse-build',
                   'LANG': 'C.UTF-8', 'PYTHONDONTWRITEBYTECODE': '1'}
    def build(*args):
        run('runuser', '-u', BUILD_USER, '--', *args, cwd=release, env=environment, timeout=600)
    python = str(release / '.venv/bin/python')
    try:
        build('python3', '-m', 'venv', str(release / '.venv'))
        build(python, '-m', 'pip', 'install', '--disable-pip-version-check',
              '-r', 'requirements.txt', '-r', 'requirements-cloud.txt')
        build(python, '-m', 'unittest', 'discover', '-s', 'tests', '-v')
        build('node', 'tests/test_frontend.cjs')
        (release / '.release').write_text(sha + '\n')
        (release / '.ready').touch()
    finally:
        # Completed releases are read-only to the app/build users.
        run('chown', '-R', 'root:root', str(release))
        run('chmod', '-R', 'go-w', str(release))
    return release


def deploy(sha=None):
    config = json.loads(CONFIG.read_text())
    repository = config['repository']
    branch = config.get('branch', 'main')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository) or branch != 'main':
        raise ValueError('Use a public owner/repository and main branch in deploy.json.')
    mirror = BASE / 'repository.git'
    if not mirror.exists():
        run('git', 'init', '--bare', str(mirror))
    run('git', '--git-dir=' + str(mirror), 'fetch', '--no-tags', '--force',
        'https://github.com/' + repository + '.git', 'refs/heads/main:refs/heads/main', timeout=120)
    head = run('git', '--git-dir=' + str(mirror), 'rev-parse', 'refs/heads/main',
               capture_output=True, text=True).stdout.strip()
    sha = sha or head
    if not re.fullmatch(r'[0-9a-f]{40}', sha):
        raise ValueError('A deployment commit must be a full Git SHA.')
    # Rollbacks may use an older tested commit, but never an unrelated branch.
    run('git', '--git-dir=' + str(mirror), 'merge-base', '--is-ancestor', sha, head)
    current = BASE / 'current'
    if current.is_symlink() and current.resolve().name == sha:
        print('Already deployed: ' + sha, flush=True)
        return
    try:
        approved = passed_ci(repository, branch, sha)
    except (OSError, ValueError) as exc:
        print('Waiting: GitHub CI result unavailable (' + type(exc).__name__ + ').', flush=True)
        return
    if not approved:
        print('Waiting for successful GitHub CI on ' + sha, flush=True)
        return
    activate(build_release(mirror, sha))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sha', help='Deploy a full SHA already tested on main; stop the timer for a rollback.')
    args = parser.parse_args()
    STATE.mkdir(parents=True, exist_ok=True)
    with (STATE / 'deploy.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('Another deployment is in progress.', flush=True)
            return 0
        try:
            deploy(args.sha)
        except Exception as exc:
            print('Deployment failed (' + type(exc).__name__ + '): ' + str(exc), flush=True)
            return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
