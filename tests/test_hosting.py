"""Public-origin validation, secure sessions and deployment rollback/gating."""
import importlib.util
import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import Mock, patch

from backend.cloud_storage import CloudStorage
from backend.server import make_server

spec = importlib.util.spec_from_file_location('twinverse_deployer', Path(__file__).resolve().parents[1]/'deploy/deploy.py')
deployer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deployer)


class HostedApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.environment = patch.dict(os.environ, {'TWINVERSE_DEVELOPER_PASSWORD': 'private-developer-test'})
        self.environment.start()
        self.server = make_server(0, Path(self.temp.name)/'hosted.sqlite3', verbose=False,
                                  faculty_password='private-faculty-test', cloud_storage=CloudStorage({}),
                                  public_origin='https://203.0.113.10')
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()
        self.server.store.db.close(); self.environment.stop(); self.temp.cleanup()

    def request(self, host='203.0.113.10', origin='https://203.0.113.10', method='GET', body=None):
        request = urllib.request.Request(f'http://127.0.0.1:{self.server.server_port}/api/session',
                    method=method, headers={'Host': host, 'Origin': origin, 'Content-Type': 'application/json'},
                    data=json.dumps(body).encode() if body is not None else None)
        try:
            return urllib.request.urlopen(request, timeout=5)
        except urllib.error.HTTPError as error:
            return error

    def test_public_host_and_https_origin_are_accepted_with_secure_cookie(self):
        with self.request(method='POST', body={'role':'faculty','password':'private-faculty-test'}) as response:
            self.assertEqual(response.status, 200)
            cookie = response.headers['Set-Cookie']
            self.assertIn('Secure', cookie); self.assertIn('HttpOnly', cookie); self.assertIn('SameSite=Strict', cookie)
        self.assertEqual(self.server.server_address[0], '127.0.0.1')

    def test_other_hosts_and_cross_origin_requests_are_rejected(self):
        for host, origin in [('attacker.example','https://203.0.113.10'),
                             ('203.0.113.10','https://attacker.example'),
                             ('203.0.113.10','http://203.0.113.10')]:
            with self.request(host, origin) as response:
                self.assertEqual(response.status, 403)

    def test_loopback_health_access_still_works(self):
        with urllib.request.urlopen(f'http://127.0.0.1:{self.server.server_port}/api/health') as response:
            self.assertEqual(json.load(response)['status'], 'ok')

    def test_invalid_origins_and_public_default_passwords_fail_before_binding(self):
        for origin in ('https://example.com/path', 'https://user:password@example.com', 'file://example.com'):
            with self.assertRaises(ValueError):make_server(0, public_origin=origin)
        with patch.dict(os.environ, {'TWINVERSE_FACULTY_PASSWORD':'', 'TWINVERSE_DEVELOPER_PASSWORD':''}):
            with self.assertRaisesRegex(ValueError, 'private'):make_server(0, public_origin='https://example.com')

    def test_database_can_live_outside_release_directory(self):
        path = Path(self.temp.name)/'persistent/workspace.sqlite3'
        with patch.dict(os.environ, {'TWINVERSE_DB_PATH':str(path)}):
            server = make_server(0, verbose=False, cloud_storage=CloudStorage({}), public_origin='')
        server.server_close(); server.store.db.close()
        self.assertTrue(path.is_file())


class DeploymentTests(unittest.TestCase):
    def test_only_exact_main_push_success_can_deploy(self):
        good = {'id':1,'run_attempt':1,'head_sha':'correct','head_branch':'main','event':'push',
                'status':'completed','conclusion':'success'}
        for change in ({'head_sha':'different'}, {'head_branch':'feature'}, {'event':'pull_request'},
                       {'status':'in_progress'}, {'conclusion':'failure'}):
            with patch.object(deployer,'read_json', return_value={'workflow_runs':[{**good,**change}]}):
                self.assertFalse(deployer.passed_ci('owner/repo','main','correct'))
        with patch.object(deployer,'read_json', return_value={'workflow_runs':[good]}):
            self.assertTrue(deployer.passed_ci('owner/repo','main','correct'))
        with patch.object(deployer,'read_json', return_value={'workflow_runs':[good,{**good,'id':2,'conclusion':'failure'}]}):
            self.assertFalse(deployer.passed_ci('owner/repo','main','correct'))

    def test_failed_health_rolls_back_to_previous_release(self):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp); old=base/'releases'/'old'; new=base/'releases'/'new'
            old.mkdir(parents=True); new.mkdir(); (base/'current').symlink_to(old)
            with patch.object(deployer,'BASE',base), patch.object(deployer,'backup_database') as backup, \
                 patch.object(deployer,'run') as run, patch.object(deployer,'await_health',side_effect=[False,True]):
                with self.assertRaisesRegex(RuntimeError, 'health'):deployer.activate(new)
            self.assertEqual((base/'current').resolve(),old.resolve())
            backup.assert_called_once()
            self.assertEqual(run.call_count,2)

    def test_successful_health_records_previous_and_new_release(self):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp); old=base/'releases'/'old'; new=base/'releases'/'new'
            old.mkdir(parents=True); new.mkdir(); (base/'current').symlink_to(old)
            with patch.object(deployer,'BASE',base), patch.object(deployer,'STATE',base), \
                 patch.object(deployer,'backup_database'), patch.object(deployer,'run'), \
                 patch.object(deployer,'await_health',return_value=True):
                deployer.activate(new)
            self.assertEqual((base/'current').resolve(),new.resolve())
            self.assertEqual(json.loads((base/'last-success.json').read_text())['previous'],'old')

    def test_live_sqlite_backup_preserves_data(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as temp:
            database=Path(temp)/'workspace.sqlite3'; backups=Path(temp)/'backups'
            with sqlite3.connect(database) as conn:
                conn.execute('CREATE TABLE records(value TEXT)'); conn.execute("INSERT INTO records VALUES ('keep me')")
            with patch.object(deployer,'DATABASE',database), patch.object(deployer,'BACKUPS',backups):
                deployer.backup_database()
            backup=next(backups.glob('*.sqlite3'))
            with sqlite3.connect(backup) as conn:
                self.assertEqual(conn.execute('SELECT value FROM records').fetchone()[0],'keep me')


if __name__ == '__main__':
    unittest.main()
