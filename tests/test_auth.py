"""Real account API tests and signed Google ID-token verification."""
import base64
import http.client
import json
import os
import secrets
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

from backend.auth import AuthError, GoogleLogin, SESSION_SECONDS, digest
from backend.cloud_storage import CloudStorage
from backend.server import make_server


class AccountClient:
    def __init__(self, server):
        self.server = server
        self.cookie = ''
        self.csrf = ''
        self.headers = {}

    def call(self, path, method='GET', body=None, csrf=True, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        values = {'Cookie': self.cookie, **(headers or {})}
        if method != 'GET' and csrf:
            values['X-CSRF-Token'] = self.csrf
        raw = json.dumps(body or {}).encode() if method in ('POST', 'PUT') else None
        if raw is not None:
            values['Content-Type'] = 'application/json'
        connection.request(method, path, raw, values)
        response = connection.getresponse()
        self.headers = dict(response.getheaders())
        if 'Set-Cookie' in self.headers:
            self.cookie = self.headers['Set-Cookie'].split(';')[0]
        data = response.read()
        result = json.loads(data) if data else {'location': self.headers.get('Location')}
        if 'csrf_token' in result:
            self.csrf = result['csrf_token']
        status = response.status
        connection.close()
        return status, result


class AccountsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name)/'workspace.sqlite3'
        self.environment = patch.dict(os.environ, {'TWINVERSE_AUTH_STORAGE': 'sqlite',
            'TWINVERSE_DEVELOPER_PASSWORD': 'private-developer-password'})
        self.environment.start()
        self.start()
        self.client = self.new_client()

    def start(self, public_origin=''):
        self.server = make_server(0, self.db, verbose=False, cloud_storage=CloudStorage({}), public_origin=public_origin)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def stop(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()
        self.server.store.db.close()

    def tearDown(self):
        self.stop(); self.environment.stop(); self.temp.cleanup()

    def new_client(self):
        client = AccountClient(self.server)
        self.assertEqual(client.call('/api/session')[0], 200)
        return client

    def signup(self, role='medical-student', client=None, email='student@example.test'):
        client = client or self.client
        status, session = client.call('/api/auth/signup', 'POST', {
            'name': 'Test User', 'email': email, 'password': 'test-password-123', 'role': role})
        self.assertEqual(status, 201, session)
        self.assertTrue(session['authenticated'])
        return session['user']

    def test_new_tables_profiles_hashes_and_normalized_email(self):
        student = self.signup(email=' STUDENT@example.test ')
        faculty = self.signup('faculty', self.new_client(), 'faculty@example.test')
        db = self.server.store.db
        self.assertEqual(student['email'], 'student@example.test')
        for table, user in [('twinverse_medical_student_profiles', student), ('twinverse_faculty_profiles', faculty)]:
            self.assertEqual(db.execute(f'SELECT user_id FROM {table}').fetchone()[0], user['id'])
        hashed = db.execute('SELECT password_hash FROM twinverse_users WHERE id=?', (student['id'],)).fetchone()[0]
        self.assertTrue(hashed.startswith('pbkdf2_sha256$600000$'))
        self.assertNotIn('password_hash', student)
        session_hash = db.execute('SELECT token_hash FROM twinverse_auth_sessions WHERE user_id=?', (student['id'],)).fetchone()[0]
        self.assertEqual(session_hash, digest(self.client.cookie.split('=', 1)[1]))
        self.assertNotIn(self.client.cookie.split('=', 1)[1], session_hash)

    def test_signup_validation_and_duplicate(self):
        body = {'name': 'Student', 'email': 'student@example.test', 'password': 'test-password', 'role': 'medical-student'}
        for changes in ({'role': 'admin'}, {'password': '123'}, {'email': 'invalid'}, {'name': ''}):
            self.assertEqual(self.client.call('/api/auth/signup', 'POST', body | changes)[0], 422)
        self.signup()
        self.assertEqual(self.client.call('/api/auth/signup', 'POST', body)[0], 409)

    def test_anonymous_access_denied_and_student_cannot_forge_role(self):
        for path in ('/api/patients', '/api/encounters', '/api/rubric', '/api/developer/data'):
            self.assertEqual(self.client.call(path)[0], 401)
        self.signup()
        self.assertEqual(self.client.call('/api/patients')[0], 200)
        self.assertEqual(self.client.call('/api/session', 'POST', {'role': 'faculty', 'password': '123'})[0], 405)
        for path in ('/api/generator/status', '/api/resources', '/api/reports', '/api/ratings/summary', '/api/developer/data', '/api/storage/status'):
            self.assertEqual(self.client.call(path, headers={'X-Role': 'faculty'})[0], 403, path)
        for path in ('/api/patients', '/api/generator/test', '/api/developer/login'):
            self.assertEqual(self.client.call(path, 'POST', {'role': 'faculty', 'password': 'private-developer-password'})[0], 403, path)

    def test_faculty_access_immediate_and_developer_has_separate_unlock(self):
        self.signup('faculty')
        for path in ('/api/resources', '/api/generator/status', '/api/storage/status'):
            self.assertEqual(self.client.call(path)[0], 200)
        self.assertEqual(self.client.call('/api/developer/data')[0], 403)
        self.assertEqual(self.client.call('/api/developer/login', 'POST', {'password': 'private-developer-password'})[0], 200)
        self.assertEqual(self.client.call('/api/developer/data')[0], 200)

    def test_csrf_and_origin_guards_cover_signup_logout_and_mutations(self):
        self.assertEqual(self.client.call('/api/auth/signup', 'POST', {}, csrf=False)[0], 403)
        self.signup()
        self.assertEqual(self.client.call('/api/auth/logout', 'POST', {}, csrf=False)[0], 403)
        self.assertEqual(self.client.call('/api/auth/logout', 'POST', {}, headers={'Origin': 'https://attacker.example'})[0], 403)
        self.assertTrue(self.client.call('/api/session')[1]['authenticated'])

    def test_faculty_review_and_rating_use_account_identity(self):
        user = self.signup('faculty')
        patient = self.client.call('/api/patients')[1]['patients'][0]
        status, encounter = self.client.call('/api/encounters', 'POST', {'patient_id': patient['id']})
        self.assertEqual(status, 201)
        path = '/api/encounters/' + encounter['id']
        status, completed = self.client.call(path+'/finish', 'POST', {})
        self.assertEqual(status, 200)
        ratings = [{'key': domain['key'], 'score': 'N/A', 'review_note': 'Not assessed in this test.', 'evidence_ids': []}
                   for domain in completed['feedback']['domains']]
        status, reviewed = self.client.call(path+'/review', 'POST', {'ratings': ratings,
            'reviewer': 'Forged name', 'review_version': completed['feedback']['review_version']})
        self.assertEqual(status, 200, reviewed)
        self.assertEqual(reviewed['feedback']['reviewer'], user['name'])
        status, rated = self.client.call(path+'/rating', 'POST', {'kind': 'auto_score', 'stars': 4, 'reviewer': 'Forged name'})
        self.assertEqual(status, 200)
        self.assertEqual(rated['ratings']['auto_score']['by'], user['name'])

    def test_login_survives_restart_logout_revokes_copied_cookie(self):
        user = self.signup()
        cookie = self.client.cookie
        headers = self.client.headers
        for text in ('HttpOnly', 'SameSite=Lax', f'Max-Age={SESSION_SECONDS}'):
            self.assertIn(text, headers['Set-Cookie'])
        self.stop(); self.start(); self.client.server = self.server
        self.assertEqual(self.client.call('/api/session')[1]['user']['id'], user['id'])
        self.assertEqual(self.client.call('/api/auth/logout', 'POST', {})[0], 200)
        self.stop(); self.start(); self.client.server = self.server
        self.assertFalse(self.client.call('/api/session')[1]['authenticated'])
        copied = self.new_client(); copied.cookie = cookie
        self.assertFalse(copied.call('/api/session')[1]['authenticated'])
        self.assertEqual(copied.call('/api/patients')[0], 401)

    def test_bad_password_login_and_session_rotation(self):
        self.signup(); old_cookie = self.client.cookie
        self.assertEqual(self.client.call('/api/auth/login', 'POST', {'email': 'student@example.test', 'password': 'wrong'})[0], 401)
        status, session = self.client.call('/api/auth/login', 'POST', {'email': 'student@example.test', 'password': 'test-password-123'})
        self.assertEqual(status, 200); self.assertNotEqual(self.client.cookie, old_cookie)
        self.assertTrue(session['authenticated'])
        old = self.new_client(); old.cookie = old_cookie
        self.assertFalse(old.call('/api/session')[1]['authenticated'])

    def test_expired_session_fails_closed(self):
        self.signup()
        self.server.store.db.execute('UPDATE twinverse_auth_sessions SET expires_at=0')
        self.server.store.db.commit()
        self.assertFalse(self.client.call('/api/session')[1]['authenticated'])
        self.assertEqual(self.client.call('/api/encounters')[0], 401)

    def test_encounter_ownership_persists_across_logins_and_denies_other_students(self):
        self.signup()
        patient = self.client.call('/api/patients')[1]['patients'][0]
        status, encounter = self.client.call('/api/encounters', 'POST', {'patient_id': patient['id']})
        self.assertEqual(status, 201, encounter)
        path = '/api/encounters/' + encounter['id']
        self.client.call('/api/auth/logout', 'POST', {})
        self.client.call('/api/auth/login', 'POST', {'email': 'student@example.test', 'password': 'test-password-123'})
        self.assertEqual(self.client.call(path)[0], 200)
        self.assertEqual(len(self.client.call('/api/encounters')[1]['encounters']), 1)
        other = self.new_client(); self.signup(client=other, email='other@example.test')
        self.assertEqual(other.call(path)[0], 403)
        self.assertEqual(other.call('/api/encounters')[1]['encounters'], [])
        faculty = self.new_client(); self.signup('faculty', faculty, 'faculty@example.test')
        self.assertEqual(faculty.call(path)[0], 200)

    def test_https_account_cookie_is_secure(self):
        self.stop(); self.start('https://example.test')
        client = AccountClient(self.server)
        self.assertEqual(client.call('/api/session', headers={'Host': 'example.test'})[0], 200)
        self.assertIn('Secure', client.headers['Set-Cookie'])

    def google_setup(self):
        self.server.google = GoogleLogin({'TWINVERSE_GOOGLE_CLIENT_ID': 'client.apps.googleusercontent.com',
            'TWINVERSE_GOOGLE_CLIENT_SECRET': 'test-secret',
            'TWINVERSE_GOOGLE_REDIRECT_URI': f'http://127.0.0.1:{self.server.server_port}/api/auth/google/callback'})
        if not self.server.google.available:
            self.skipTest('Install requirements-auth.txt for Google OAuth tests.')

    def begin_google(self, client=None, intent='signup', role='medical-student'):
        client = client or self.client
        status, data = client.call('/api/auth/google/start', 'POST', {'intent': intent, 'role': role})
        self.assertEqual(status, 200, data)
        query = parse_qs(urlsplit(data['url']).query)
        self.assertEqual(query['code_challenge_method'], ['S256'])
        self.assertEqual(query['scope'], ['openid email profile'])
        self.assertNotIn('test-secret', data['url'])
        return query['state'][0]

    def test_google_callback_is_bound_to_browser_and_one_use_role_cannot_change(self):
        self.google_setup(); state = self.begin_google(role='faculty')
        stranger = self.new_client()
        self.assertIn('expired', stranger.call('/api/auth/google/callback?state=' + state + '&code=code')[1]['location'])
        claims = {'sub': 'google-user', 'email': 'google@example.test', 'email_verified': True, 'name': 'Google User'}
        with patch.object(self.server.google, 'claims', return_value=claims) as verify:
            self.assertEqual(self.client.call('/api/auth/google/callback?state=' + state + '&code=code')[1]['location'], '/#cases')
            self.assertEqual(self.client.call('/api/session')[1]['user']['role'], 'faculty')
            self.assertIn('expired', self.client.call('/api/auth/google/callback?state=' + state + '&code=code')[1]['location'])
            verify.assert_called_once()
            self.client.call('/api/auth/logout', 'POST', {})
            another = self.begin_google(role='medical-student')
            self.client.call('/api/auth/google/callback?state=' + another + '&code=code')
            self.assertEqual(self.client.call('/api/session')[1]['user']['role'], 'faculty')

    def test_google_does_not_auto_link_password_account_and_link_requires_matching_user(self):
        self.google_setup(); user = self.signup()
        claims = {'sub': 'google-student', 'email': user['email'], 'email_verified': True, 'name': 'Google Student'}
        self.client.call('/api/auth/logout', 'POST', {})
        state = self.begin_google(role='faculty')
        with patch.object(self.server.google, 'claims', return_value=claims):
            result = self.client.call('/api/auth/google/callback?state=' + state + '&code=code')[1]
            self.assertIn('password', result['location'])
            self.assertFalse(self.client.call('/api/session')[1]['authenticated'])
            self.client.call('/api/auth/login', 'POST', {'email': user['email'], 'password': 'test-password-123'})
            state = self.begin_google(intent='link')
            self.client.call('/api/auth/google/callback?state=' + state + '&code=code')
            linked = self.client.call('/api/session')[1]['user']
            self.assertEqual(linked['id'], user['id']); self.assertTrue(linked['has_google'])
            self.assertEqual(linked['role'], 'medical-student')

    def test_google_expired_cancelled_unverified_and_unknown_login_are_rejected(self):
        self.google_setup()
        state = self.begin_google()
        self.server.store.db.execute('UPDATE twinverse_oauth_states SET expires_at=0'); self.server.store.db.commit()
        self.assertIn('expired', self.client.call('/api/auth/google/callback?state=' + state + '&code=c')[1]['location'])
        state = self.begin_google()
        self.assertIn('cancelled', self.client.call('/api/auth/google/callback?state=' + state + '&error=access_denied')[1]['location'])
        state = self.begin_google()
        with patch.object(self.server.google, 'claims', return_value={'sub': 's', 'email': 'x@example.test', 'email_verified': False}):
            self.assertIn('verified', self.client.call('/api/auth/google/callback?state=' + state + '&code=c')[1]['location'])
        state = self.begin_google(intent='login')
        with patch.object(self.server.google, 'claims', return_value={'sub': 's', 'email': 'x@example.test', 'email_verified': True}):
            self.assertIn('Create', self.client.call('/api/auth/google/callback?state=' + state + '&code=c')[1]['location'])
        self.assertFalse(self.client.call('/api/session')[1]['authenticated'])

    def test_google_callback_must_match_browser_origin(self):
        self.google_setup()
        self.server.google.redirect_uri = 'http://localhost:8000/api/auth/google/callback'
        status, result = self.client.call('/api/auth/google/start', 'POST', {'intent': 'login'})
        self.assertEqual(status, 400); self.assertIn('localhost:8000', result['error'])


class GoogleTokenTests(unittest.TestCase):
    def test_public_ip_callback_disabled_and_localhost_domain_callbacks_supported(self):
        env = {'TWINVERSE_GOOGLE_CLIENT_ID': 'client', 'TWINVERSE_GOOGLE_CLIENT_SECRET': 'secret'}
        provider = GoogleLogin(env | {'TWINVERSE_GOOGLE_REDIRECT_URI': 'https://44.246.200.136/api/auth/google/callback'})
        self.assertFalse(provider.available)
        for uri in ('http://127.0.0.1:8000/api/auth/google/callback', 'https://twinverse.example.com/api/auth/google/callback'):
            provider = GoogleLogin(env | {'TWINVERSE_GOOGLE_REDIRECT_URI': uri})
            try:
                import google.auth
            except ImportError:
                self.skipTest('Install requirements-auth.txt.')
            self.assertTrue(provider.available)

    def test_signed_id_token_audience_issuer_expiry_nonce_and_signature_verified(self):
        try:
            from cryptography.hazmat.primitives.asymmetric import rsa
            from cryptography.hazmat.primitives import serialization
            from google.auth import crypt, jwt
        except ImportError:
            self.skipTest('Install requirements-auth.txt.')
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
        cert = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
        signer = crypt.RSASigner.from_string(pem, key_id='test-key')
        provider = GoogleLogin({'TWINVERSE_GOOGLE_CLIENT_ID': 'client.apps.googleusercontent.com',
            'TWINVERSE_GOOGLE_CLIENT_SECRET': 'test-secret',
            'TWINVERSE_GOOGLE_REDIRECT_URI': 'http://127.0.0.1:8000/api/auth/google/callback'})
        payload = {'sub': 'google-user', 'email': 'g@example.test', 'email_verified': True,
            'iss': 'https://accounts.google.com', 'aud': provider.client_id, 'iat': int(time.time()),
            'exp': int(time.time()) + 3600, 'nonce': 'expected-nonce'}
        state = {'redirect_uri': provider.redirect_uri, 'nonce': 'expected-nonce', 'code_verifier': secrets.token_urlsafe(32)}
        def verify(changes=None, corrupt=False):
            token = jwt.encode(signer, payload | (changes or {})).decode()
            if corrupt:
                parts = token.split('.'); parts[2] = base64.urlsafe_b64encode(b'wrong-signature').decode().rstrip('='); token = '.'.join(parts)
            response = Mock(); response.json.return_value = {'id_token': token}
            transport = Mock(return_value=Mock(status=200, data=json.dumps({'test-key': cert}).encode()))
            with patch('requests.post', return_value=response) as exchange, patch('google.auth.transport.requests.Request', return_value=transport):
                claims = provider.claims('authorization-code', state)
                self.assertEqual(exchange.call_args.kwargs['data']['code_verifier'], state['code_verifier'])
                return claims
        self.assertEqual(verify()['sub'], 'google-user')
        for changes in ({'aud': 'attacker-client'}, {'iss': 'https://attacker.example'}, {'exp': int(time.time())-60}, {'nonce': 'wrong'}):
            with self.assertRaises(AuthError):
                verify(changes)
        with self.assertRaises(AuthError):
            verify(corrupt=True)


if __name__ == '__main__':
    unittest.main()
