"""Optional approval storage: immutable PostgreSQL versions and private S3 files.

Run `python3 -m backend.cloud_storage check` or `... init-db` after configuring
.env. Publishing never creates buckets, databases, users, or IAM policies.
"""
import argparse
import copy
import hashlib
import ipaddress
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TABLE = 'public.twinverse_patient_versions'
SCHEMA_FILE = ROOT / 'backend' / 'sql' / 'cloud_storage.sql'


class CloudStorageError(Exception):
    """A safe message suitable for showing to faculty; never raw SDK errors."""


def load_environment():
    """Existing environment variables take precedence over the local .env file."""
    path = Path(os.environ.get('TWINVERSE_ENV_FILE') or ROOT / '.env')
    if not path.is_file():
        return
    try:
        from dotenv import load_dotenv
    except ImportError:
        raise CloudStorageError('Install requirements-cloud.txt to load the .env configuration.') from None
    load_dotenv(path, override=False, interpolate=False)


class CloudStorage:
    def __init__(self, env=None):
        env = os.environ if env is None else env
        self.mode = env.get('TWINVERSE_CLOUD_STORAGE', 'local').strip().lower()
        self.bucket = env.get('TWINVERSE_S3_BUCKET', '').strip()
        self.prefix = env.get('TWINVERSE_S3_PREFIX', 'twinverse').strip('/')
        self.region = env.get('AWS_REGION') or env.get('AWS_DEFAULT_REGION') or 'us-west-2'
        self.profile = env.get('AWS_PROFILE') or None
        self.owner = env.get('TWINVERSE_S3_EXPECTED_OWNER', '').strip()
        self.kms_key = env.get('TWINVERSE_S3_KMS_KEY_ID', '').strip()
        self.pg_auth = env.get('TWINVERSE_PG_AUTH', 'password').strip().lower()
        self.pg_region = env.get('TWINVERSE_PG_REGION') or self.region
        self.errors = []
        self.pg = {key: env.get(name, '').strip() for key, name in (
            ('host', 'PGHOST'), ('hostaddr', 'PGHOSTADDR'), ('port', 'PGPORT'), ('dbname', 'PGDATABASE'),
            ('user', 'PGUSER'), ('sslmode', 'PGSSLMODE'), ('sslrootcert', 'PGSSLROOTCERT'))}
        # Preserve whitespace in passwords. libpq can also use a .pgpass file.
        if self.pg_auth == 'password' and env.get('PGPASSWORD') is not None:
            self.pg['password'] = env['PGPASSWORD']
        self.pg['port'] = self.pg['port'] or '5432'
        self.pg['sslmode'] = self.pg['sslmode'] or 'verify-full'
        self.pg = {key: value for key, value in self.pg.items() if value != ''}
        self.pg.update(connect_timeout=30, options='-c statement_timeout=30000 -c lock_timeout=10000')
        self._pg_address_hint = None
        if self.mode not in ('local', 'aws'):
            self.errors.append('TWINVERSE_CLOUD_STORAGE must be local or aws.')
        if self.enabled:
            if self.pg_auth not in ('password', 'iam'):
                self.errors.append('TWINVERSE_PG_AUTH must be password or iam.')
            if not self.bucket:
                self.errors.append('Set TWINVERSE_S3_BUCKET.')
            for name in ('PGHOST', 'PGDATABASE', 'PGUSER'):
                if not env.get(name, '').strip():
                    self.errors.append(f'Set {name}.')
            if not self.pg['port'].isdigit() or not 1 <= int(self.pg['port']) <= 65535:
                self.errors.append('PGPORT must be a port number from 1 to 65535.')
            if self.pg['sslmode'] not in ('require', 'verify-ca', 'verify-full'):
                self.errors.append('PGSSLMODE must require TLS: require, verify-ca, or verify-full.')
            if self.owner and not re.fullmatch(r'\d{12}', self.owner):
                self.errors.append('TWINVERSE_S3_EXPECTED_OWNER must be a 12-digit account ID.')
            if not re.fullmatch(r'[A-Za-z0-9/_-]*', self.prefix):
                self.errors.append('TWINVERSE_S3_PREFIX may contain letters, numbers, /, _, and -.')

    @property
    def enabled(self):
        # Invalid modes also fail closed, never silently falling back to local.
        return self.mode != 'local'

    def status(self):
        return {'mode': self.mode, 'enabled': self.enabled,
                'configured': not self.errors, 'errors': self.errors, 'postgres_auth': self.pg_auth}

    def require_config(self):
        if self.errors:
            raise CloudStorageError('Cloud storage configuration is incomplete. ' + ' '.join(self.errors))
        if not self.enabled:
            raise CloudStorageError('AWS storage is off. Set TWINVERSE_CLOUD_STORAGE=aws first.')

    def _connect(self):
        try:
            import psycopg
        except ImportError:
            raise CloudStorageError('Install requirements-cloud.txt to use PostgreSQL storage.') from None
        for attempt in range(2):
            params = dict(self.pg)
            # A successful gateway address is a hint, not a replacement hostname.
            # Keep the configured hostname for certificate checks and IAM signing.
            if self._pg_address_hint and 'hostaddr' not in params:
                params['hostaddr'] = self._pg_address_hint
            if self.pg_auth == 'iam':
                params['password'] = self._iam_token()
            try:
                connection = psycopg.connect(**params)
                address = getattr(getattr(connection, 'info', None), 'hostaddr', None)
                if isinstance(address, str) and 'hostaddr' not in self.pg:
                    try:
                        self._pg_address_hint = str(ipaddress.ip_address(address))
                    except ValueError:
                        pass
                return connection
            except Exception as exc:
                self._pg_address_hint = None
                operational_error = getattr(psycopg, 'OperationalError', None)
                state = getattr(exc, 'sqlstate', None)
                transient = (isinstance(operational_error, type)
                             and isinstance(exc, operational_error)
                             and (state is None or state.startswith('08') or state == '57P03'))
                # Authentication and certificate failures need configuration fixes.
                # Only retry opening a connection, never a query or transaction.
                configuration_failure = any(term in str(exc).lower() for term in (
                    'certificate', 'does not match host name', 'authentication failed',
                    'permission denied', 'no pg_hba.conf entry'))
                if attempt == 0 and transient and not configuration_failure:
                    continue
                if self.pg_auth == 'iam':
                    raise CloudStorageError('PostgreSQL IAM connection failed. Check current AWS credentials, IAM database authentication, the rds_iam database role, rds-db:connect permission, TLS, and network access.') from None
                raise CloudStorageError('PostgreSQL connection failed. Check the endpoint, database login, TLS certificate, and network access.') from None

    def _aws_client(self, service, region=None):
        try:
            import boto3
            from botocore.config import Config
        except ImportError:
            raise CloudStorageError('Install requirements-cloud.txt to use AWS storage.') from None
        try:
            # Normal AWS credential chain: env, named profiles, SSO, and instance roles.
            return boto3.Session(profile_name=self.profile, region_name=region or self.region).client(
                service, config=Config(connect_timeout=10, read_timeout=30,
                                    retries={'mode': 'standard', 'total_max_attempts': 3}))
        except Exception:
            raise CloudStorageError('AWS credentials could not be loaded. Check the AWS profile or refresh your workshop session.') from None

    def _s3(self):
        return self._aws_client('s3')

    def _iam_token(self):
        # Generate on every new connection; never cache/store a 15-minute token.
        try:
            return self._aws_client('rds', self.pg_region).generate_db_auth_token(
                DBHostname=self.pg['host'], Port=int(self.pg['port']),
                DBUsername=self.pg['user'], Region=self.pg_region)
        except CloudStorageError:
            raise
        except Exception:
            raise CloudStorageError('Could not generate a PostgreSQL IAM token. Refresh the AWS credentials and check the endpoint, database username, and region.') from None

    def _bucket_args(self):
        args = {'Bucket': self.bucket}
        if self.owner:
            args['ExpectedBucketOwner'] = self.owner
        return args

    def publish(self, profile, attachments):
        """Upload binaries first; commit the profile+manifest in one PG transaction.

        Keys contain patient ID, version, attachment ID and content hash. A retry
        reuses the same objects. A failed PG commit can leave unreferenced files;
        they are never exposed as a successfully published case by the app.
        """
        if not self.enabled:
            return None
        self.require_config()
        stage = 'database'
        try:
            with self._connect() as conn:
                # Fail before uploading anything if the table/login is unavailable.
                conn.execute(f'SELECT patient_id FROM {TABLE} LIMIT 0')
                s3 = self._s3()
                manifest = []
                stage = 's3'
                for metadata, raw in attachments:
                    digest = hashlib.sha256(raw).hexdigest()
                    if metadata.get('sha256') and metadata['sha256'] != digest:
                        raise CloudStorageError('An attachment failed its integrity check. Attach the file again before approving.')
                    name = re.sub(r'[^A-Za-z0-9._-]', '_', Path(metadata['name']).name)[:120] or 'file'
                    relative = f"patients/{profile['id']}/v{profile['version']}/{metadata['id']}/{digest}/{name}"
                    key = f'{self.prefix}/{relative}' if self.prefix else relative
                    args = {**self._bucket_args(), 'Key': key, 'Body': raw,
                            'ContentType': metadata['mime'], 'Metadata': {'sha256': digest}}
                    # Otherwise inherit the existing bucket's encryption policy.
                    # No ACLs or bucket policy changes are required.
                    if self.kms_key:
                        args.update(ServerSideEncryption='aws:kms', SSEKMSKeyId=self.kms_key)
                    s3.put_object(**args)
                    manifest.append({**metadata, 'sha256': digest, 's3_bucket': self.bucket,
                                     's3_key': key, 's3_uri': f's3://{self.bucket}/{key}'})
                receipt = {'provider': 'aws', 'patient_id': profile['id'],
                           'version': profile['version'], 'file_count': len(manifest),
                           'saved_at': profile['approved_at']}
                stored_profile = copy.deepcopy(profile)
                stored_profile['cloud_storage'] = receipt
                stage = 'database'
                conn.execute(f'''
                    INSERT INTO {TABLE} (patient_id, version, profile, files, approved_at)
                    VALUES (%s, %s, %s::jsonb, %s::jsonb, %s)
                    ON CONFLICT (patient_id, version) DO UPDATE
                    SET profile=EXCLUDED.profile, files=EXCLUDED.files, approved_at=EXCLUDED.approved_at
                ''', (profile['id'], profile['version'], json.dumps(stored_profile),
                      json.dumps(manifest), profile['approved_at']))
            # The connection context commits before a success receipt is returned.
            return receipt
        except CloudStorageError:
            raise
        except Exception as exc:
            if stage == 's3':
                # Only surface a known AWS error code, never raw exception text.
                code = getattr(exc, 'response', {}).get('Error', {}).get('Code', '')
                detail = f' ({code})' if code in (
                    'AccessDenied', 'InvalidToken', 'ExpiredToken', 'NoSuchBucket',
                    'InvalidAccessKeyId', 'SignatureDoesNotMatch') else ''
                raise CloudStorageError(f'S3 upload failed{detail}. Check the bucket, region, upload permissions, and current AWS credentials.') from None
            raise CloudStorageError('PostgreSQL save failed. Check that the storage table exists and the database login has SELECT, INSERT, and UPDATE permissions.') from None

    def init_db(self):
        self.require_config()
        try:
            with self._connect() as conn:
                conn.execute(SCHEMA_FILE.read_text())
        except CloudStorageError:
            raise
        except Exception:
            raise CloudStorageError('Table setup failed. Ask the database owner to run backend/sql/cloud_storage.sql, or grant CREATE on the public schema.') from None

    def check(self):
        """Read-only connectivity check. Does not claim to verify write access."""
        self.require_config()
        results = []
        try:
            with self._connect() as conn:
                conn.execute(f'SELECT patient_id, version, profile, files FROM {TABLE} LIMIT 0')
                row = conn.execute('''SELECT
                    has_table_privilege(current_user, %s, 'SELECT'),
                    has_table_privilege(current_user, %s, 'INSERT'),
                    has_table_privilege(current_user, %s, 'UPDATE')''', (TABLE, TABLE, TABLE)).fetchone()
                if not all(row):
                    raise CloudStorageError('PostgreSQL login needs SELECT, INSERT, and UPDATE on the storage table.')
            results.append({'service': 'postgresql', 'ok': True, 'message': 'Connected; storage table and read/write grants found.'})
        except Exception as exc:
            message = str(exc) if isinstance(exc, CloudStorageError) else 'PostgreSQL table check failed. Initialize the table or ask its owner for access.'
            results.append({'service': 'postgresql', 'ok': False, 'message': message})
        try:
            self._s3().head_bucket(**self._bucket_args())
            results.append({'service': 's3', 'ok': True, 'message': 'Bucket reachable. Upload permission is verified on the first approval.'})
        except Exception as exc:
            message = str(exc) if isinstance(exc, CloudStorageError) else 'S3 bucket check failed. Check AWS credentials, region, owner, and s3:ListBucket permission.'
            results.append({'service': 's3', 'ok': False, 'message': message})
        return results


def main():
    parser = argparse.ArgumentParser(description='Configure/check approval storage without changing AWS infrastructure.')
    parser.add_argument('command', choices=('check', 'init-db'))
    args = parser.parse_args()
    try:
        load_environment()
        storage = CloudStorage()
        if args.command == 'init-db':
            storage.init_db()
            print('PostgreSQL approval storage table is ready.')
            return 0
        results = storage.check()
        for result in results:
            print(f"{'OK' if result['ok'] else 'FAILED'} {result['service']}: {result['message']}")
        return 0 if all(result['ok'] for result in results) else 1
    except CloudStorageError as exc:
        print(f'FAILED: {exc}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
