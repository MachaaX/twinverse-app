"""Persistent user accounts, password login, and Google authorization-code login.

AWS mode uses the existing approval storage PostgreSQL connection and IAM/TLS
settings. Local mode uses the workspace SQLite database, with the same schema.
"""
import argparse
import base64
import hashlib
import ipaddress
import os
import re
import secrets
import time
import urllib.parse
import uuid
from contextlib import contextmanager
from pathlib import Path

from .cloud_storage import CloudStorage, CloudStorageError, load_environment

SCHEMA = Path(__file__).parent / 'sql' / 'auth.sql'
PASSWORD_ITERATIONS = 600_000
SESSION_SECONDS = 30 * 24 * 60 * 60
OAUTH_SECONDS = 600
ROLES = {'medical-student', 'faculty'}


class AuthError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message
        super().__init__(message)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def csrf_token(token):
    return digest('csrf:' + token)


def clean_email(value):
    if not isinstance(value, str):
        raise AuthError(422, 'Enter a valid email address.')
    value = value.strip().lower()
    if len(value) > 254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value):
        raise AuthError(422, 'Enter a valid email address.')
    return value


def clean_name(value):
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 120:
        raise AuthError(422, 'Enter your name using 1–120 characters.')
    return value.strip()


def clean_role(value):
    if not isinstance(value, str) or value not in ROLES:
        raise AuthError(422, 'Choose Medical student or Faculty.')
    return value


def password_hash(password):
    if not isinstance(password, str) or not 8 <= len(password) <= 128:
        raise AuthError(422, 'Use a password of 8–128 characters.')
    salt = secrets.token_bytes(16)
    result = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, PASSWORD_ITERATIONS)
    return f'pbkdf2_sha256${PASSWORD_ITERATIONS}${salt.hex()}${result.hex()}'


def password_matches(password, encoded):
    # A dummy hash makes unknown-email and password-account failures comparable.
    if not isinstance(password, str) or len(password) > 128:
        return False
    try:
        algorithm, iterations, salt, expected = (encoded or
            f'pbkdf2_sha256${PASSWORD_ITERATIONS}$' + '00' * 16 + '$' + '00' * 32).split('$')
        if algorithm != 'pbkdf2_sha256' or not 600_000 <= int(iterations) <= 2_000_000:
            return False
        actual = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), int(iterations))
        return bool(encoded) and secrets.compare_digest(actual.hex(), expected)
    except (ValueError, TypeError):
        return False


def public_user(row):
    return {key: row[key] for key in ('id', 'name', 'email', 'role')} | {
        'has_google': bool(row.get('google_sub')), 'has_password': bool(row.get('password_hash'))}


class _Connection:
    def __init__(self, connection, postgres):
        self.connection, self.postgres = connection, postgres

    def execute(self, sql, params=()):
        return self.connection.execute(sql.replace('?', '%s') if self.postgres else sql, params)


class AuthStore:
    def __init__(self, store=None, cloud=None, mode=None):
        self.store = store
        self.cloud = cloud or CloudStorage()
        self.mode = mode or os.environ.get('TWINVERSE_AUTH_STORAGE') or (
            'postgres' if self.cloud.enabled else 'sqlite')
        if self.mode not in ('postgres', 'sqlite'):
            raise ValueError('TWINVERSE_AUTH_STORAGE must be postgres or sqlite.')
        if self.mode == 'sqlite':
            if store is None:
                raise ValueError('Local account storage needs the workspace database.')
            with store.lock:
                store.db.execute('PRAGMA foreign_keys=ON')
                store.db.executescript(SCHEMA.read_text())
                store.db.commit()

    @contextmanager
    def connection(self):
        try:
            if self.mode == 'postgres':
                from psycopg.rows import dict_row
                with self.cloud._connect() as connection:
                    connection.row_factory = dict_row
                    yield _Connection(connection, True)
            else:
                with self.store.lock, self.store.db:
                    yield _Connection(self.store.db, False)
        except AuthError:
            raise
        except Exception as exc:
            if getattr(exc, 'sqlstate', '') == '23505':
                raise AuthError(409, 'An account with this email or Google identity already exists.') from None
            # Do not expose DB credentials, SQL, or personally identifying data.
            raise AuthError(503, 'Account storage is unavailable. Check the database connection and initialize the account tables.') from None

    def init_db(self):
        with self.connection() as connection:
            for statement in SCHEMA.read_text().split(';'):
                if statement.strip():
                    connection.execute(statement)

    def _create(self, connection, name, email, role, hashed=None, google_sub=None):
        if connection.execute('SELECT id FROM twinverse_users WHERE email=?', (email,)).fetchone():
            raise AuthError(409, 'An account with this email already exists. Sign in instead.')
        user_id = str(uuid.uuid4())
        connection.execute('INSERT INTO twinverse_users (id,email,name,role,password_hash,google_sub,created_at) VALUES (?,?,?,?,?,?,?)',
                           (user_id, email, name, role, hashed, google_sub, int(time.time())))
        table = 'twinverse_faculty_profiles' if role == 'faculty' else 'twinverse_medical_student_profiles'
        connection.execute(f'INSERT INTO {table} (user_id) VALUES (?)', (user_id,))
        return public_user(dict(connection.execute('SELECT * FROM twinverse_users WHERE id=?', (user_id,)).fetchone()))

    def signup(self, name, email, password, role):
        name, email, role = clean_name(name), clean_email(email), clean_role(role)
        hashed = password_hash(password)
        with self.connection() as connection:
            return self._create(connection, name, email, role, hashed=hashed)

    def login(self, email, password):
        try:
            email = clean_email(email)
        except AuthError:
            email = ''
        with self.connection() as connection:
            row = connection.execute('SELECT * FROM twinverse_users WHERE email=?', (email,)).fetchone()
        user = dict(row) if row else None
        if not password_matches(password, user['password_hash'] if user else None):
            raise AuthError(401, 'Incorrect email or password.')
        return public_user(user)

    def create_session(self, user_id, previous_token=''):
        token = secrets.token_urlsafe(32)
        current = int(time.time())
        with self.connection() as connection:
            connection.execute('DELETE FROM twinverse_auth_sessions WHERE expires_at<=?', (current,))
            if previous_token:
                connection.execute('DELETE FROM twinverse_auth_sessions WHERE token_hash=?', (digest(previous_token),))
            connection.execute('INSERT INTO twinverse_auth_sessions (token_hash,user_id,created_at,expires_at) VALUES (?,?,?,?)',
                               (digest(token), user_id, current, current + SESSION_SECONDS))
        return token

    def lookup(self, token):
        with self.connection() as connection:
            row = connection.execute('''SELECT u.* FROM twinverse_users u JOIN twinverse_auth_sessions s ON s.user_id=u.id
                WHERE s.token_hash=? AND s.expires_at>?''', (digest(token), int(time.time()))).fetchone()
        return public_user(dict(row)) if row else None

    def logout(self, token):
        with self.connection() as connection:
            connection.execute('DELETE FROM twinverse_auth_sessions WHERE token_hash=?', (digest(token),))
            connection.execute('DELETE FROM twinverse_oauth_states WHERE browser_hash=?', (digest(token),))

    def google_user(self, claims, state, current_user=None):
        subject = claims.get('sub')
        if not isinstance(subject, str) or not 1 <= len(subject) <= 255 or claims.get('email_verified') is not True:
            raise AuthError(401, 'Google did not provide a verified email address.')
        email = clean_email(claims.get('email'))
        with self.connection() as connection:
            row = connection.execute('SELECT * FROM twinverse_users WHERE google_sub=?', (subject,)).fetchone()
            if state['intent'] == 'link':
                if not current_user or current_user['id'] != state['user_id'] or current_user['email'] != email:
                    raise AuthError(403, 'Sign in to the matching account before linking Google.')
                if row and row['id'] != current_user['id']:
                    raise AuthError(409, 'This Google account is already linked to another profile.')
                connection.execute('UPDATE twinverse_users SET google_sub=? WHERE id=?', (subject, current_user['id']))
                return public_user(dict(connection.execute('SELECT * FROM twinverse_users WHERE id=?', (current_user['id'],)).fetchone()))
            if row:
                # A new role selection cannot change a registered account's role.
                return public_user(dict(row))
            if state['intent'] != 'signup':
                raise AuthError(401, 'Create an account and choose your role before signing in with Google.')
            if connection.execute('SELECT id FROM twinverse_users WHERE email=?', (email,)).fetchone():
                raise AuthError(409, 'Sign in with your password, then link Google from your account menu.')
            return self._create(connection, clean_name(claims.get('name') or email.split('@')[0]), email,
                                clean_role(state['role']), google_sub=subject)

    def save_oauth(self, browser_token, intent, role, user_id, redirect_uri):
        state, nonce, verifier = (secrets.token_urlsafe(32) for _ in range(3))
        current = int(time.time())
        with self.connection() as connection:
            connection.execute('DELETE FROM twinverse_oauth_states WHERE expires_at<=? OR browser_hash=?',
                               (current, digest(browser_token)))
            connection.execute('''INSERT INTO twinverse_oauth_states
                (state_hash,browser_hash,nonce,code_verifier,intent,role,user_id,redirect_uri,expires_at)
                VALUES (?,?,?,?,?,?,?,?,?)''',
                (digest(state), digest(browser_token), nonce, verifier, intent, role, user_id, redirect_uri, current + OAUTH_SECONDS))
        return state, nonce, verifier

    def consume_oauth(self, state, browser_token):
        if not isinstance(state, str) or not 20 <= len(state) <= 100:
            raise AuthError(401, 'Google sign-in expired. Start again.')
        with self.connection() as connection:
            row = connection.execute('''DELETE FROM twinverse_oauth_states
                WHERE state_hash=? AND browser_hash=? AND expires_at>? RETURNING *''',
                (digest(state), digest(browser_token), int(time.time()))).fetchone()
        if not row:
            raise AuthError(401, 'Google sign-in expired. Start again.')
        return dict(row)


class GoogleLogin:
    def __init__(self, env=None):
        env = os.environ if env is None else env
        self.client_id = env.get('TWINVERSE_GOOGLE_CLIENT_ID', '').strip()
        self.client_secret = env.get('TWINVERSE_GOOGLE_CLIENT_SECRET', '').strip()
        self.redirect_uri = env.get('TWINVERSE_GOOGLE_REDIRECT_URI', '').strip()

    @property
    def available(self):
        if not (self.client_id and self.client_secret and self.redirect_uri):
            return False
        try:
            uri = urllib.parse.urlsplit(self.redirect_uri)
            uri.port
        except ValueError:
            return False
        if (not uri.hostname or uri.username or uri.password or uri.query or uri.fragment
                or uri.path != '/api/auth/google/callback'):
            return False
        if uri.hostname in ('localhost', '127.0.0.1', '::1'):
            if uri.scheme not in ('http', 'https'):
                return False
        else:
            if uri.scheme != 'https':
                return False
            try:
                ipaddress.ip_address(uri.hostname)
                return False
            except ValueError:
                pass
        try:
            import google.oauth2.id_token
            import google.auth.transport.requests
            return True
        except ImportError:
            return False

    def start(self, store, browser_token, intent, role=None, user=None, origin=None):
        if not self.available:
            raise AuthError(503, 'Google sign-in is not configured yet. Use email and password.')
        uri = urllib.parse.urlsplit(self.redirect_uri)
        if origin and origin != f'{uri.scheme}://{uri.netloc}':
            raise AuthError(400, f'Open TwinVerse at {uri.scheme}://{uri.netloc} to use Google sign-in.')
        if intent not in ('login', 'signup', 'link'):
            raise AuthError(422, 'Choose login or signup.')
        role = clean_role(role) if intent == 'signup' else None
        if intent == 'link' and not user:
            raise AuthError(401, 'Sign in before linking Google.')
        state, nonce, verifier = store.save_oauth(browser_token, intent, role,
                                                 user['id'] if intent == 'link' else None, self.redirect_uri)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
        return 'https://accounts.google.com/o/oauth2/v2/auth?' + urllib.parse.urlencode({
            'client_id': self.client_id, 'redirect_uri': self.redirect_uri, 'response_type': 'code',
            'scope': 'openid email profile', 'state': state, 'nonce': nonce,
            'code_challenge': challenge, 'code_challenge_method': 'S256', 'prompt': 'select_account'})

    def claims(self, code, state):
        if not self.available or state['redirect_uri'] != self.redirect_uri:
            raise AuthError(401, 'Google sign-in configuration changed. Start again.')
        if not isinstance(code, str) or not 1 <= len(code) <= 4096:
            raise AuthError(401, 'Google sign-in was not completed.')
        try:
            import requests
            data = {'code': code, 'client_id': self.client_id,
                'client_secret': self.client_secret, 'redirect_uri': self.redirect_uri,
                'grant_type': 'authorization_code', 'code_verifier': state['code_verifier']}
            response = requests.post('https://oauth2.googleapis.com/token', data=data, timeout=15)
            response.raise_for_status()
            tokens = response.json()
            from google.auth.transport.requests import Request
            from google.oauth2.id_token import verify_oauth2_token
            transport = Request()
            bounded_request = lambda *args, **kwargs: transport(*args, **{**kwargs, 'timeout': 15})
            claims = verify_oauth2_token(tokens['id_token'], bounded_request, self.client_id)
            if not secrets.compare_digest(str(claims.get('nonce', '')), state['nonce']):
                raise ValueError('Nonce mismatch')
            return claims
        except Exception:
            raise AuthError(401, 'Google identity verification failed. Start sign-in again.') from None


def main():
    parser = argparse.ArgumentParser(description='Initialize account tables in the existing PostgreSQL database.')
    parser.add_argument('command', choices=('init-db', 'check'))
    args = parser.parse_args()
    try:
        load_environment()
        store = AuthStore(cloud=CloudStorage(), mode='postgres')
        if args.command == 'init-db':
            store.init_db()
            print('PostgreSQL user, role-profile, session, and Google state tables are ready.')
        else:
            with store.connection() as connection:
                for table in ('twinverse_users', 'twinverse_medical_student_profiles', 'twinverse_faculty_profiles',
                              'twinverse_auth_sessions', 'twinverse_oauth_states'):
                    connection.execute(f'SELECT * FROM {table} LIMIT 0')
            print('PostgreSQL account tables are reachable.')
        return 0
    except (AuthError, CloudStorageError) as exc:
        print('FAILED: ' + str(exc))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
