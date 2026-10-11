# Accounts and Google sign-in

- Signup accepts name, email, password (8–128 characters), and Medical student or Faculty. Faculty gets access immediately. The old shared faculty password is replaced by personal accounts.
- The top-right account circle and bottom-left identity tile show your name, role, and **Log out**. Login survives browser/server restarts for up to 30 days. Logout revokes that session. Account profiles, password hashes, session hashes, and one-use Google state are stored in the database; they are not stored in S3.
- Students can access the practice library, their encounters/history, and assessment rubric. Faculty additionally get Patient Studio, generation, source materials, review/report pages, and the separately locked Developer view. The server checks every protected API request.

## Local Google setup

- The supplied client ID/secret are already saved in the private, Git-ignored `.env` file. Do not put them in source files or frontend JavaScript.
- Install dependencies using the project virtual environment:

  ```bash
  .venv/bin/python -m pip install -r requirements.txt -r requirements-cloud.txt -r requirements-auth.txt
  ```

- Open [Google Auth Platform → Clients](https://console.cloud.google.com/auth/clients), select the supplied **Web application** client, and add this exact **Authorized redirect URI**:

  ```text
  http://127.0.0.1:8000/api/auth/google/callback
  ```

- If Google returns `redirect_uri_mismatch`, add the exact callback above to finish Google setup. Save the Google client configuration. If your Google application is in Testing, add your Google account under **Audience → Test users**. No frontend Google SDK or JavaScript-origin entry is required for this server-side redirect flow. See [Google's web server OAuth setup](https://developers.google.com/identity/protocols/oauth2/web-server).
- Run `.venv/bin/python run.py` and open `http://127.0.0.1:8000/#signup`. Choose a role first, then **Continue with Google**. Subsequent sign-in uses **Continue with Google** on the Sign in tab. Your saved role does not change when signing in.
- Use the same hostname and port as the configured callback. If you use another port, update `TWINVERSE_GOOGLE_REDIRECT_URI` and the Google client's registered URI to match.
- To add Google to an existing email/password account, sign in with the password first, then choose **Link Google** in your account menu. The Google email must match. Signup never silently merges a Google identity into an existing password account.

## PostgreSQL account tables

- AWS account storage uses the same `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, TLS certificate, and IAM/password configuration as patient approvals. Set `TWINVERSE_AUTH_STORAGE=postgres` in the private environment. No new PostgreSQL endpoint or AWS IAM administrator permission is needed when the existing database login can create these tables.
- Initialize the schema once on the machine that can reach PostgreSQL:

  ```bash
  .venv/bin/python -m backend.auth init-db
  .venv/bin/python -m backend.auth check
  ```

- On EC2, use the root-owned environment file without printing its secrets:

  ```bash
  cd /opt/twinverse/current
  sudo env TWINVERSE_ENV_FILE=/etc/twinverse/app.env .venv/bin/python -m backend.auth init-db
  sudo env TWINVERSE_ENV_FILE=/etc/twinverse/app.env .venv/bin/python -m backend.auth check
  ```

- The schema adds `twinverse_users`, `twinverse_medical_student_profiles`, `twinverse_faculty_profiles`, `twinverse_auth_sessions`, and `twinverse_oauth_states`. Existing patient-version tables are preserved. Schema initialization is explicit; normal requests do not create tables. Missing tables or unavailable PostgreSQL fail closed instead of silently switching databases.
- This checkout is configured to use the same PostgreSQL database through a running local-only EC2 SSH tunnel. If the tunnel stops, reopen it before starting the app (leave this terminal running):

  ```bash
  ssh -F /dev/null -i ~/Desktop/twinverse-key.pem -o IdentitiesOnly=yes \
    -o StrictHostKeyChecking=yes -o UserKnownHostsFile=/private/tmp/twinverse-ec2-known-hosts \
    -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -N \
    -L 127.0.0.1:5432:database-1.cluster-c5sig0eiuu7v.us-west-2.rds.amazonaws.com:5432 \
    ubuntu@44.246.200.136
  ```

- For standalone local development without AWS networking, explicitly set `TWINVERSE_AUTH_STORAGE=sqlite`; accounts then live in `data/twinverse.sqlite3`. SQLite accounts are separate from PostgreSQL accounts. A local app using private RDS needs VPN/VPC access or an SSH tunnel through EC2. `PGHOSTADDR=127.0.0.1` can route a tunnel while `PGHOST` stays the real RDS hostname for TLS verification and IAM token signing.
- New encounters belong to the account ID and remain accessible after logging out and back in. Existing anonymous demo encounters stay accessible to faculty; they are not reassigned to new students.

## Google on EC2

- The supplied Google credentials are saved in `/etc/twinverse/app.env` with root-only permissions.
- The public app is now `https://patientzero.me`. EC2 has trusted HTTPS and sets `TWINVERSE_PUBLIC_ORIGIN=https://patientzero.me` and `TWINVERSE_GOOGLE_REDIRECT_URI=https://patientzero.me/api/auth/google/callback`. The old IP and `www` redirect to this canonical address.
- The Google Web application client now registers exactly `https://patientzero.me/api/auth/google/callback`, preserving the local callback. Google sign-in is enabled by the app, and an anonymous browser reaches Google's sign-in page without callback or client errors. Completing registration or login requires your interactive Google sign-in. Follow the [domain and Google setup walkthrough](DOMAIN_SETUP.md). Existing accounts remain in PostgreSQL; sign in again on the new domain because IP-address cookies do not transfer.

## Verification

- Run `.venv/bin/python -m unittest discover -s tests -v` and `node tests/test_frontend.cjs`.
- Account tests exercise role checks, password hashing, cross-origin/CSRF checks, account ownership, restart persistence, session rotation/revocation, one-use Google state, and signed Google ID-token verification including wrong audience, issuer, nonce, expired tokens, and invalid signatures.
- Real Google consent needs your interactive Google login and the registered callback. Automated tests use signed test identities; they do not log into your Google account.
