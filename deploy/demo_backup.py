"""Private demo PostgreSQL/SQLite backups; no AWS credentials are required."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess

root = Path('/var/backups/twinverse/demo-auto')
root.mkdir(parents=True, exist_ok=True, mode=0o700)
stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
stage = root / ('.pending-' + stamp)
stage.mkdir(mode=0o700)
try:
    dump = stage / 'demo-postgres.pgdump'
    with dump.open('wb') as out:
        dump.chmod(0o600)
        subprocess.run(['runuser','-u','postgres','--','pg_dump','-Fc','--no-owner',
            '--no-privileges','twinverse_demo_20261011'],stdout=out,check=True)
    workspace = stage / 'workspace.sqlite3'
    with sqlite3.connect('/var/lib/twinverse/twinverse.sqlite3', timeout=30) as source, sqlite3.connect(workspace) as target:
        source.backup(target)
        assert target.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        counts={name:target.execute('SELECT count(*) FROM '+name).fetchone()[0]
                for name in ['cases','encounters','attachments','reply_cache','speech_jobs']}
    workspace.chmod(0o600)
    manifest={'created_at_utc':stamp,'postgres_database':'twinverse_demo_20261011',
              'workspace_counts':counts,'files':{}}
    for path in (dump,workspace):
        manifest['files'][path.name]={'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    path=stage/'manifest.json'
    path.write_text(json.dumps(manifest,indent=2)+'\n');path.chmod(0o600)
    final=root/stamp
    stage.rename(final)
    for old in sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith('.'))[:-24]:
        shutil.rmtree(old)
    print('Private demo database backup completed: '+str(final),flush=True)
except Exception:
    shutil.rmtree(stage,ignore_errors=True)
    raise
