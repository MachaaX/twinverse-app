"""Cloud publication failures, ordering and API integration (no AWS account needed)."""
import base64
import copy
import hashlib
import importlib.util
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from backend.cloud_storage import CloudStorage, CloudStorageError
from backend.seed import seed_profiles
from backend.server import make_server
from test_app import Client


ENV = {'TWINVERSE_CLOUD_STORAGE': 'aws', 'TWINVERSE_S3_BUCKET': 'test-bucket',
       'TWINVERSE_S3_EXPECTED_OWNER': '454105254021', 'PGHOST': 'database.example',
       'PGDATABASE': 'twinverse', 'PGUSER': 'app', 'PGPASSWORD': 'TOP-SECRET'}


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.storage = CloudStorage(ENV)
        self.conn = Mock()
        self.conn.__enter__ = Mock(return_value=self.conn)
        self.conn.__exit__ = Mock(return_value=False)
        self.storage._connect = Mock(return_value=self.conn)
        self.s3 = Mock()
        self.storage._s3 = Mock(return_value=self.s3)
        self.profile = {'id': 'patient-id', 'version': 2, 'approved_at': '2026-10-10T16:00:00Z',
                        'name': 'Synthetic patient', 'facts': [{'record': 'Synthetic fact'}]}
        self.raw = b'synthetic report'
        self.metadata = {'id': 'attachment-id', 'name': 'lab report.txt', 'mime': 'text/plain',
                         'kind': 'source', 'sha256': hashlib.sha256(self.raw).hexdigest()}

    def test_local_mode_is_dependency_free(self):
        local = CloudStorage({})
        local._connect = Mock(side_effect=AssertionError('Do not connect'))
        self.assertIsNone(local.publish(self.profile, []))
        self.assertFalse(local.status()['enabled'])

    def test_invalid_or_incomplete_config_never_falls_back(self):
        for env in ({'TWINVERSE_CLOUD_STORAGE': 'oops'}, {'TWINVERSE_CLOUD_STORAGE': 'aws'},
                    {**ENV, 'PGSSLMODE': 'disable'}, {**ENV, 'PGPORT': 'invalid'},
                    {**ENV, 'TWINVERSE_PG_AUTH': 'invalid'}):
            storage = CloudStorage(env)
            self.assertTrue(storage.enabled)
            with self.assertRaises(CloudStorageError):storage.publish(self.profile, [])
            self.assertNotIn('TOP-SECRET', json.dumps(storage.status()))

    def test_upload_then_commit_profile_and_source_manifest(self):
        calls = []
        self.conn.execute.side_effect = lambda *args: calls.append('database')
        self.s3.put_object.side_effect = lambda **kwargs: calls.append('upload')
        receipt = self.storage.publish(self.profile, [(self.metadata, self.raw)])
        self.assertEqual(calls, ['database', 'upload', 'database'])
        args = self.s3.put_object.call_args.kwargs
        self.assertEqual(args['Body'], self.raw)
        self.assertEqual(args['ExpectedBucketOwner'], ENV['TWINVERSE_S3_EXPECTED_OWNER'])
        self.assertNotIn('ACL', args)
        self.assertTrue(args['Key'].endswith('/lab_report.txt'))
        params = self.conn.execute.call_args.args[1]
        stored, files = json.loads(params[2]), json.loads(params[3])
        self.assertEqual(stored['facts'], self.profile['facts'])
        self.assertEqual(stored['cloud_storage'], receipt)
        self.assertEqual(files[0]['kind'], 'source')
        self.assertEqual(files[0]['s3_uri'], 's3://test-bucket/' + args['Key'])
        self.assertNotIn('cloud_storage', self.profile)
        self.conn.__exit__.assert_called_once_with(None, None, None)

    def test_iam_generates_fresh_token_for_each_connection(self):
        storage = CloudStorage({**ENV, 'TWINVERSE_PG_AUTH': 'iam'})
        storage._iam_token = Mock(side_effect=['temporary-token-one', 'temporary-token-two'])
        driver = Mock()
        with patch.dict('sys.modules', {'psycopg': driver}):
            storage._connect();storage._connect()
        self.assertEqual([call.kwargs['password'] for call in driver.connect.call_args_list],
                         ['temporary-token-one', 'temporary-token-two'])
        self.assertNotIn('password', storage.pg)
        self.assertEqual(storage.status()['postgres_auth'], 'iam')
        self.assertNotIn('temporary-token', json.dumps(storage.status()))

    def test_iam_signing_uses_database_endpoint_user_and_region(self):
        storage = CloudStorage({**ENV, 'TWINVERSE_PG_AUTH': 'iam',
                                'AWS_REGION': 'us-west-2', 'TWINVERSE_PG_REGION': 'us-east-1'})
        client = Mock()
        client.generate_db_auth_token.return_value = 'temporary-token'
        storage._aws_client = Mock(return_value=client)
        self.assertEqual(storage._iam_token(), 'temporary-token')
        storage._aws_client.assert_called_once_with('rds', 'us-east-1')
        client.generate_db_auth_token.assert_called_once_with(
            DBHostname='database.example', Port=5432, DBUsername='app', Region='us-east-1')

    def test_iam_connection_failure_does_not_expose_token(self):
        storage = CloudStorage({**ENV, 'TWINVERSE_PG_AUTH': 'iam'})
        storage._iam_token = Mock(return_value='SECRET-IAM-TOKEN')
        driver = Mock()
        driver.connect.side_effect = RuntimeError('password=SECRET-IAM-TOKEN')
        with patch.dict('sys.modules', {'psycopg': driver}):
            with self.assertRaisesRegex(CloudStorageError, 'IAM connection failed') as caught:
                storage._connect()
        self.assertNotIn('SECRET-IAM-TOKEN', str(caught.exception))

    def test_same_version_retry_uses_same_s3_keys(self):
        self.storage.publish(self.profile, [(self.metadata, self.raw)])
        first = self.s3.put_object.call_args.kwargs['Key']
        self.storage.publish(self.profile, [(self.metadata, self.raw)])
        self.assertEqual(self.s3.put_object.call_args.kwargs['Key'], first)
        self.profile['version'] += 1
        self.storage.publish(self.profile, [(self.metadata, self.raw)])
        self.assertNotEqual(self.s3.put_object.call_args.kwargs['Key'], first)

    def test_s3_failure_rolls_back_and_never_writes_profile(self):
        error = RuntimeError('TOP-SECRET')
        error.response = {'Error': {'Code': 'AccessDenied'}}
        self.s3.put_object.side_effect = error
        with self.assertRaisesRegex(CloudStorageError, 'AccessDenied') as caught:
            self.storage.publish(self.profile, [(self.metadata, self.raw)])
        self.assertNotIn('TOP-SECRET', str(caught.exception))
        self.assertEqual(self.conn.execute.call_count, 1)
        self.assertIsNotNone(self.conn.__exit__.call_args.args[0])

    def test_database_commit_failure_does_not_return_success(self):
        self.conn.__exit__.side_effect = RuntimeError('password=TOP-SECRET')
        with self.assertRaisesRegex(CloudStorageError, 'PostgreSQL save failed') as caught:
            self.storage.publish(self.profile, [(self.metadata, self.raw)])
        self.assertNotIn('TOP-SECRET', str(caught.exception))

    def test_missing_table_fails_before_s3_upload(self):
        self.conn.execute.side_effect = RuntimeError('relation does not exist')
        with self.assertRaises(CloudStorageError):self.storage.publish(self.profile, [(self.metadata, self.raw)])
        self.s3.put_object.assert_not_called()

    def test_integrity_failure_does_not_upload_corrupt_file(self):
        with self.assertRaisesRegex(CloudStorageError, 'integrity'):
            self.storage.publish(self.profile, [(self.metadata, b'changed')])
        self.s3.put_object.assert_not_called()

    def test_kms_setting_is_only_applied_when_requested(self):
        self.storage.kms_key = 'test-key'
        self.storage.publish(self.profile, [(self.metadata, self.raw)])
        args = self.s3.put_object.call_args.kwargs
        self.assertEqual((args['ServerSideEncryption'], args['SSEKMSKeyId']), ('aws:kms', 'test-key'))

    @unittest.skipUnless(importlib.util.find_spec('boto3'), 'optional boto3 dependency not installed')
    def test_upload_arguments_are_accepted_by_real_aws_sdk(self):
        import boto3
        from botocore.stub import Stubber
        client = boto3.client('s3', region_name='us-west-2',
                              aws_access_key_id='test', aws_secret_access_key='test')
        key = f"twinverse/patients/patient-id/v2/attachment-id/{self.metadata['sha256']}/lab_report.txt"
        expected = {'Bucket': 'test-bucket', 'ExpectedBucketOwner': '454105254021',
                    'Key': key, 'Body': self.raw, 'ContentType': 'text/plain',
                    'Metadata': {'sha256': self.metadata['sha256']}}
        self.storage._s3.return_value = client
        with Stubber(client) as stub:
            stub.add_response('put_object', {}, expected)
            self.storage.publish(self.profile, [(self.metadata, self.raw)])
            stub.assert_no_pending_responses()


class CloudPublishApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.storage = CloudStorage(ENV)
        self.storage.publish = Mock(side_effect=lambda p, files: {
            'provider': 'aws', 'patient_id': p['id'], 'version': p['version'],
            'file_count': len(files), 'saved_at': p['approved_at']})
        self.server = make_server(0, Path(self.temp.name)/'test.sqlite3', verbose=False,
                                  faculty_password='test-token', cloud_storage=self.storage)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.client = Client(f'http://127.0.0.1:{self.server.server_port}')
        self.client.call('/api/session', 'POST', {'role': 'faculty', 'password': 'test-token'})
        profile = copy.deepcopy(seed_profiles()[0])
        status, data = self.client.call('/api/patients', 'POST', {'profile': profile})
        self.assertEqual(status, 201)
        self.profile = data['profile']
        self.path = '/api/patients/' + self.profile['id']

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join()
        self.server.store.db.close();self.temp.cleanup()

    def approve(self, **body):
        return self.client.call(self.path+'/publish', 'POST', {'approved': True, **body})

    def test_cloud_copy_happens_only_on_approved_publish(self):
        self.storage.publish.assert_not_called()
        payload = {'name': 'report.pdf', 'content': base64.b64encode(b'%PDF synthetic test').decode(),
                   'kind': 'artifact', 'release': 'initial', 'keywords': []}
        self.assertEqual(self.client.call(self.path+'/attachments', 'POST', payload)[0], 201)
        self.storage.publish.assert_not_called()
        self.assertEqual(self.client.call(self.path+'/publish', 'POST', {'approved': False})[0], 422)
        self.storage.publish.assert_not_called()
        status, data = self.approve(draft_version=0)
        self.assertEqual(status, 200, data)
        p, files = self.storage.publish.call_args.args
        self.assertEqual(p['status'], 'published')
        self.assertEqual(files[0][1], b'%PDF synthetic test')
        self.assertEqual(data['profile']['cloud_storage']['file_count'], 1)
        self.assertTrue(data['storage']['enabled'])

    def test_failure_keeps_previous_version_and_retry_can_succeed(self):
        self.assertEqual(self.approve()[0], 200)
        previous = self.client.call(self.path)[1]['profile']
        edited = {**previous, 'name': 'Changed draft'}
        status, data = self.client.call(self.path, 'PUT', {'profile': edited})
        self.assertEqual(status, 200)
        draft = data['profile']
        self.storage.publish.side_effect = CloudStorageError('S3 upload failed (AccessDenied).')
        status, data = self.approve()
        self.assertEqual(status, 502, data)
        self.assertIn('preserved', data['error'])
        local = self.server.store.get('cases', self.profile['id'])
        self.assertEqual(local['published'], previous)
        self.assertEqual(local['draft'], draft)
        self.storage.publish.side_effect = lambda p, files: {'provider': 'aws', 'version': p['version'], 'file_count': len(files)}
        status, data = self.approve()
        self.assertEqual(status, 200, data)
        self.assertEqual(data['profile']['version'], draft['version']+1)

    def test_student_and_stale_draft_cannot_publish(self):
        self.assertEqual(self.approve(draft_version=99)[0], 409)
        self.client.call('/api/session', 'POST', {'role': 'student'})
        self.assertEqual(self.approve()[0], 403)
        self.assertEqual(self.client.call('/api/storage/status')[0], 403)
        self.storage.publish.assert_not_called()

    def test_incomplete_cloud_config_blocks_publication(self):
        self.server.cloud_storage = CloudStorage({'TWINVERSE_CLOUD_STORAGE': 'aws'})
        status, result = self.approve()
        self.assertEqual(status, 502, result)
        self.assertIsNone(self.server.store.get('cases', self.profile['id'])['published'])

    def test_pending_publish_blocks_mutations_but_not_readers(self):
        entered, finish = threading.Event(), threading.Event()
        def publish(p, files):
            entered.set()
            if not finish.wait(4):raise CloudStorageError('test timed out')
            return {'provider': 'aws', 'version': p['version'], 'file_count': len(files)}
        self.storage.publish.side_effect = publish
        result = []
        thread = threading.Thread(target=lambda: result.append(self.approve()))
        thread.start()
        try:
            self.assertTrue(entered.wait(2))
            self.assertEqual(self.client.call('/api/patients')[0], 200)
            self.assertEqual(self.client.call(self.path)[0], 200)
            self.assertEqual(self.client.call(self.path, 'PUT', {'profile': self.profile})[0], 409)
            self.assertEqual(self.client.call(self.path, 'DELETE')[0], 409)
            self.assertEqual(self.client.call(self.path+'/attachments', 'POST', {})[0], 409)
            self.assertEqual(self.approve()[0], 409)
        finally:
            finish.set();thread.join(4)
        self.assertEqual(result[0][0], 200, result)
        self.assertEqual(self.server.publishing_cases, set())


@unittest.skipUnless(os.environ.get('TWINVERSE_TEST_PGHOST'), 'optional real PostgreSQL test not configured')
class RealPostgresTests(unittest.TestCase):
    """Set TWINVERSE_TEST_PGHOST/PORT/USER/DATABASE/SSLROOTCERT for a disposable DB."""
    def test_real_sql_transaction_and_version_rows(self):
        env = {**ENV, 'PGPASSWORD': ''}
        for name in ('HOST', 'PORT', 'USER', 'DATABASE', 'SSLROOTCERT'):
            if os.environ.get('TWINVERSE_TEST_PG'+name):
                env['PG'+name] = os.environ['TWINVERSE_TEST_PG'+name]
        storage = CloudStorage(env)
        storage.init_db()
        storage._s3 = Mock(return_value=Mock())
        pid = 'cloud-integration-test'
        profile = {'id': pid, 'version': 1, 'approved_at': '2026-10-10T16:00:00Z',
                   'facts': [{'record': "Unicode: café, 'quotes', and clinical facts"}]}
        metadata = {'id': 'test-report', 'name': 'clinical.txt', 'mime': 'text/plain', 'kind': 'artifact'}
        try:
            self.assertTrue(all(result['ok'] for result in storage.check()))
            storage.publish(profile, [(metadata, b'clinical file')])
            storage.publish(profile, [(metadata, b'clinical file')])
            profile['version'] = 2
            storage.publish(profile, [])
            broken = {**profile, 'version': 3, 'approved_at': 'invalid timestamp'}
            with self.assertRaises(CloudStorageError):storage.publish(broken, [(metadata, b'clinical file')])
            with storage._connect() as conn:
                rows = conn.execute('SELECT version, profile, files FROM public.twinverse_patient_versions WHERE patient_id=%s ORDER BY version', (pid,)).fetchall()
            self.assertEqual([row[0] for row in rows], [1, 2])
            self.assertEqual(rows[0][1]['facts'], profile['facts'])
            self.assertTrue(rows[0][2][0]['s3_uri'].startswith('s3://test-bucket/'))
            self.assertEqual(rows[1][2], [])
        finally:
            with storage._connect() as conn:
                conn.execute('DELETE FROM public.twinverse_patient_versions WHERE patient_id=%s', (pid,))
