# Connect faculty approvals to AWS PostgreSQL and S3

With AWS storage enabled, **Approve & publish** copies attached files (TXT, PDF,
images, and other supported uploads) to S3 and commits the approved patient profile
plus its file manifest to PostgreSQL. Publication becomes available locally only
after both succeed. **Save draft** and file uploads stay local until approval.

You do not need AWS administrator access to use existing resources. You do need a
working AWS session with S3 upload permissions, a PostgreSQL database login, and
network access to the database. A bucket URL or database hostname alone is not an
authentication credential.

## IAM authentication for the database endpoint you supplied

- The local `.env` is configured for
  `database-1.cluster-c5sig0eiuu7v.us-west-2.rds.amazonaws.com`, port `5432`,
  database `postgres`, user `postgres`, and your temporary workshop AWS
  environment credentials. `AWS_PROFILE` is omitted so the SDK uses those
  credentials. The local `.env` is ignored by Git and restricted to your user
  (`chmod 600 .env`); never copy its secrets into source files or the frontend.
- `TWINVERSE_PG_AUTH=iam` generates a fresh IAM token for every PostgreSQL
  connection. `TWINVERSE_PG_REGION=us-west-2` selects the database's region.
  The app does not store/cache tokens, and ignores `PGPASSWORD` in IAM mode.
  Tokens are valid for 15 minutes; the underlying workshop AWS credentials must
  also be valid. [AWS IAM authentication](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/UsingWithRDS.IAMDBAuth.html)
- When your workshop session expires, refresh `AWS_ACCESS_KEY_ID`,
  `AWS_SECRET_ACCESS_KEY`, and `AWS_SESSION_TOKEN` together in the ignored `.env`
  from **Workshop Studio → AWS account access → Get AWS CLI credentials**, then
  restart the app. Alternatively use a named profile as described below,
  remove these three values from `.env`, and set `AWS_PROFILE=workshop`.
  A database auth token alone cannot generate future tokens or authorize S3 uploads.
- Live verification succeeded with this setup: faculty approval committed a
  synthetic profile to PostgreSQL and uploaded TXT/PDF files to S3. Downloads
  matched the original bytes and hashes. The verification's test records and
  objects were then removed; existing records were untouched.
- The resource owner must enable IAM database authentication, grant `rds_iam`
  to the database login, and allow your AWS identity `rds-db:connect` for that
  cluster's database user. Generating a signed token alone does not prove those
  permissions are present. [AWS PostgreSQL IAM prerequisites](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/UsingWithRDS.IAMDBAuth.DBAccounts.html)
- This workshop endpoint's TLS certificate verifies with the Mac's system CA
  bundle, so its local `.env` uses `PGSSLROOTCERT=/etc/ssl/cert.pem` and
  `PGSSLMODE=verify-full`. The RDS-only CA bundle did not verify its certificate
  chain. Use the appropriate CA bundle for any other database endpoint.
- After refreshing your local AWS credentials, run `python3 -m
  backend.cloud_storage init-db`, then `python3 -m backend.cloud_storage check`,
  and restart the app. The initializer only creates the app's approval table; it
  does not change database users, IAM policies, or cluster settings.
- Use the provided `postgres` login only if your workshop authorizes it. An
  application-specific database login with the required table grants can be
  substituted through `PGUSER` once the owner provisions its IAM access.

## Step-by-step setup for your workshop account

- **1. Obtain an existing PostgreSQL database.** If you do not already have one,
  ask your workshop organizer/resource owner to provision an **RDS PostgreSQL**
  database, or an **Aurora PostgreSQL writer endpoint**, and provide its endpoint,
  port (usually `5432`), database name, database username, and password through your
  normal private channel. An AWS console password or Bedrock API key is not a
  PostgreSQL password. If the workshop allows you to create RDS resources, the
  organizer can instead walk you through **RDS → Databases → Create database →
  PostgreSQL**; that is a separate, billable infrastructure action, not something
  this app performs.

- **2. Confirm the connection route.** In **RDS → Databases → your database →
  Connectivity & security**, copy the endpoint and port. A private RDS endpoint
  usually requires a VPN, an existing approved tunnel, or running the app inside
  the VPC. Ask the owner to allow PostgreSQL connections from the app host through
  the appropriate security group. For a permitted public endpoint, use an inbound
  rule limited to your own IP, rather than opening the database to everyone. If
  your role cannot change networking, the owner must arrange it. [AWS connection
  guide](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_CommonTasks.Connect.html)

- **3. Confirm access to your existing S3 bucket.** Use
  `twinverse-s3-bucket-1` in `us-west-2`, account `454105254021`. The app needs
  `s3:PutObject` under `twinverse/*`. `s3:GetObject` lets you retrieve/verify cloud
  files, and `s3:ListBucket` lets the diagnostic command check the bucket. If its
  existing encryption policy uses SSE-KMS, ask for the corresponding KMS grants;
  the app can send the required KMS key ID. The app uses the existing bucket's
  encryption settings and does not change its policy, ACLs, or public-access
  settings. Uploads run from the Python backend, so browser CORS configuration is
  unnecessary. [AWS PutObject permissions](https://docs.aws.amazon.com/boto3/latest/reference/services/s3/client/put_object.html)

- **4. Refresh your workshop credentials.** Return to **Workshop Studio → AWS
  account access → Get AWS CLI credentials**. Save all three values from the same
  session in a named profile called `workshop` in `~/.aws/credentials`. Preserve
  existing profiles and append/update only this section:

  ```ini
  [workshop]
  aws_access_key_id = YOUR_WORKSHOP_ACCESS_KEY
  aws_secret_access_key = YOUR_WORKSHOP_SECRET_KEY
  aws_session_token = YOUR_WORKSHOP_SESSION_TOKEN
  ```

  Keep credentials out of committed files and the browser. Workshop credentials
  expire: refresh the three values together when necessary. The app reads the
  named profile on each approval. To use the provided `export` credentials instead,
  omit `AWS_PROFILE` and either start the app from that same terminal or put the
  three values in the ignored, private `.env`. Restart after updating `.env`;
  already-exported shell variables take precedence over it.
  [AWS temporary credentials](https://docs.aws.amazon.com/cli/v1/userguide/cli-configure-files.html)

- **5. Install the optional storage dependencies.** From the project directory:

  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  python3 -m pip install -r requirements-cloud.txt
  ```

  This installs Boto3, Psycopg, and dotenv. If you also use live Bedrock generation,
  install the existing `requirements.txt` in that environment as well. The core
  local app continues to work without these optional storage packages.

- **6. Download the RDS TLS certificate bundle.** This validates the database
  server's certificate and hostname:

  ```bash
  mkdir -p certs
  curl --fail --location https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem \
    --output certs/rds-global-bundle.pem
  ```

  [AWS PostgreSQL TLS instructions](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/PostgreSQL.Concepts.General.SSL.html)

- **7. Set the server configuration.** Copy the example only if you do not already
  have a `.env` file, then edit `.env` locally. It is ignored by Git and is loaded
  automatically by `run.py` and the storage diagnostic command. Existing shell
  environment variables take precedence.

  ```bash
  cp -n .env.example .env
  ```

  Fill in these settings using the database owner's values:

  ```dotenv
  TWINVERSE_CLOUD_STORAGE=aws
  TWINVERSE_S3_BUCKET=twinverse-s3-bucket-1
  TWINVERSE_S3_PREFIX=twinverse
  TWINVERSE_S3_EXPECTED_OWNER=454105254021
  AWS_REGION=us-west-2
  AWS_PROFILE=workshop
  PGHOST=YOUR_DATABASE_ENDPOINT.rds.amazonaws.com
  PGPORT=5432
  PGDATABASE=twinverse
  PGUSER=twinverse_app
  PGPASSWORD="YOUR_DATABASE_PASSWORD"
  PGSSLMODE=verify-full
  PGSSLROOTCERT=./certs/rds-global-bundle.pem
  ```

  `PGHOST` is the hostname, without `https://`. `PGDATABASE` must name an existing
  database. If you use an existing instance role or AWS environment credentials
  instead of a named profile, remove `AWS_PROFILE`. For an existing KMS requirement,
  also set `TWINVERSE_S3_KMS_KEY_ID` to the owner's key ARN. On this Mac, if Python
  reports a CA certificate error for S3, add `AWS_CA_BUNDLE=/etc/ssl/cert.pem` to
  `.env`; keep PostgreSQL's RDS certificate setting above.

- **8. Create the storage table once.** If your database login has `CREATE` on the
  `public` schema, run:

  ```bash
  python3 -m backend.cloud_storage init-db
  ```

  Otherwise give the database owner `backend/sql/cloud_storage.sql` and ask them
  to run it. Your app login then needs `CONNECT` on the database, `USAGE` on the
  `public` schema, and `SELECT, INSERT, UPDATE` on
  `public.twinverse_patient_versions`. No database superuser privilege is needed.
  The app does not create tables automatically when faculty publish.

- **9. Check connectivity.** Run:

  ```bash
  python3 -m backend.cloud_storage check
  ```

  Expect `OK postgresql` and `OK s3`. This command is read-only: it checks the
  PostgreSQL table and grants and S3 bucket access. Actual S3 `PutObject`
  permission is confirmed on the first approval. A role limited to `PutObject`
  can publish even if this bucket check fails because it lacks `ListBucket`.

- **10. Start the app and approve a synthetic test patient.** Restart any existing
  server process, then run:

  ```bash
  python3 run.py
  ```

  Sign in as Faculty, open Patient Studio, create/save a patient, attach a small
  synthetic TXT or PDF, check the review checkbox, and click **Approve & publish**.
  The button displays **Saving to AWS…**, followed by **Saved to AWS** after
  successful storage. If either service fails, the app reports the failure and
  preserves the saved draft and previous published version. Fix the connection
  and approve again.

- **11. Verify the stored files and profile.** In **S3 → twinverse-s3-bucket-1 →
  Objects**, open `twinverse/patients/<patient-id>/v<version>/`. Each attachment
  has its own ID and content hash in its key. In your PostgreSQL client, run:

  ```sql
  SELECT patient_id, version, profile->>'name' AS patient_name,
         jsonb_array_length(files) AS file_count, approved_at
  FROM public.twinverse_patient_versions
  ORDER BY approved_at DESC;
  ```

  The `profile` column contains the full approved profile as JSONB, and `files`
  contains each file's S3 bucket/key/URI, MIME type, hash, and release metadata.
  The database does not store the file bytes. Source files retain their
  faculty-only classification; downloading through the app still applies its
  existing authorization and disclosure rules.

## What to ask the resource owner for

You can copy this request into your normal channel:

> Please provide an existing RDS/Aurora PostgreSQL writer endpoint, port, database
> name, and an application database login. Please arrange network access from my
> app host and run `backend/sql/cloud_storage.sql`. The app login needs CONNECT,
> USAGE on public, and SELECT/INSERT/UPDATE on public.twinverse_patient_versions.
> My workshop role also needs PutObject/GetObject on
> arn:aws:s3:::twinverse-s3-bucket-1/twinverse/* and ListBucket on the bucket for
> diagnostics. If the bucket requires SSE-KMS, please provide the key ARN and
> required key permissions. I do not need AWS administrator privileges.

## Troubleshooting and storage boundaries

- **S3 InvalidToken/ExpiredToken:** obtain a fresh workshop credential set and
  update the named profile's access key, secret key, and session token together.
- **S3 AccessDenied:** the resource owner must grant upload access to the object
  prefix; being able to view the bucket in the console does not prove you can
  upload using the terminal's identity. Check KMS grants if applicable.
- **PostgreSQL connection timeout:** confirm the endpoint/port and your permitted
  VPC/VPN/tunnel/security-group route. Changing the hostname does not open a
  network route.
- **PostgreSQL connection/authentication/TLS failure:** verify the database login
  and database name, CA file, and hostname. For IAM mode, confirm the `rds_iam`
  role and `rds-db:connect` grant. For password mode, use a normal database password
  or libpq password file.
- **Missing table or database permissions:** the owner must initialize the table
  and grant access. The app will not use a console role to bypass PostgreSQL grants.
- **Cloud configuration incomplete:** fill in the missing server settings and
  restart. AWS mode blocks publication instead of silently saving only locally.
- **Return to local mode:** set `TWINVERSE_CLOUD_STORAGE=local` and restart. The UI
  explicitly reports that approvals are saved on this computer.
- **Data boundaries:** this feature archives newly approved versions to AWS.
  Existing patients are copied when next approved; drafts, encounters, sessions,
  and the application's working files continue to use local SQLite. There is no
  automatic restore from PostgreSQL/S3, and deleting a local patient does not
  erase its approved cloud history. Keep the local database and files.
- **Partial failures:** S3 and PostgreSQL do not share a transaction. If S3 uploads
  succeed but the database write fails, some objects can remain unreferenced.
  Retrying an unchanged draft reuses deterministic keys. The app only reports
  successful publication after the database commit and local save finish.

## Implementation references

- [Psycopg connection contexts commit on success and roll back on exceptions](https://www.psycopg.org/psycopg3/docs/basic/usage.html)
- [AWS RDS PostgreSQL connection and TLS guidance](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/PostgreSQL.Concepts.General.SSL.html)
- [AWS S3 PutObject API](https://docs.aws.amazon.com/boto3/latest/reference/services/s3/client/put_object.html)
