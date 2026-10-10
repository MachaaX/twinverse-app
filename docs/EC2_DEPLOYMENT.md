# EC2 hosting and continuous deployment

- **Website:** `https://44.246.200.136`.
- **Server:** `i-068fa2275326642f9` (`twinverse`), Ubuntu 24.04, `us-west-2`.
- **GitHub source:** [MachaaX/twinverse-app](https://github.com/MachaaX/twinverse-app), branch `main`.
- **Flow:** push to `main` → GitHub Actions runs backend/frontend checks → EC2
  checks for a successful run every 90–100 seconds → builds/tests that exact
  commit → backs up SQLite → switches release → restarts and checks health.
  An unhealthy release rolls back automatically. A failed/pending CI run leaves
  the current website running. [GitHub workflow runs API](https://docs.github.com/en/rest/actions/workflow-runs)
- The EC2 timer pulls the public repository. It needs no GitHub token, GitHub SSH
  secret, AWS administrator permission, self-hosted Actions runner, or webhook
  exposed to the internet. The app's AWS credentials stay in its server-only
  environment file.

## Publish a change

- Edit the app and run its checks locally:

  ```bash
  source .venv/bin/activate
  python -m unittest discover -s tests -v
  node tests/test_frontend.cjs
  ```

- Commit and push to `main`, or merge a reviewed PR into `main`:

  ```bash
  git add YOUR_CHANGED_FILES
  git commit -m "Describe your change"
  git push origin main
  ```

- Watch [GitHub Actions](https://github.com/MachaaX/twinverse-app/actions).
  After **TwinVerse CI** succeeds, allow roughly two minutes plus dependency
  installation time for deployment. Production also repeats the tests before
  activating the release.
- Check `https://44.246.200.136/api/health`: its `release` field contains the
  deployed commit SHA. Refresh the website after that SHA matches your commit.
  Faculty/developer access needs a new sign-in after a restart.

## Server access and logs

- Connect using your existing private SSH key:

  ```bash
  ssh -i ~/Desktop/twinverse-key.pem ubuntu@44.246.200.136
  ```

- View status/logs:

  ```bash
  sudo systemctl status twinverse twinverse-deploy.timer
  sudo journalctl -u twinverse -n 50 --no-pager
  sudo journalctl -u twinverse-deploy -n 80 --no-pager
  sudo cat /var/lib/twinverse-deploy/last-success.json
  ```

- Trigger a check immediately:

  ```bash
  sudo systemctl start twinverse-deploy.service
  ```

## Credentials and application data

- `/etc/twinverse/app.env` contains temporary AWS credentials, existing S3/RDS
  settings, and private faculty/developer passwords. It is readable only by root;
  systemd supplies the values to the app. It is outside all releases and Git.
- The corresponding private local file is `.env.hosted` (Git-ignored, mode `0600`).
  Open it locally to find `TWINVERSE_FACULTY_PASSWORD` and
  `TWINVERSE_DEVELOPER_PASSWORD`. The public deployment rejects the repository's
  default passwords.
- When workshop credentials expire, get a fresh matching access key, secret key,
  and session token. On EC2, edit only those three values and restart:

  ```bash
  sudoedit /etc/twinverse/app.env
  sudo systemctl restart twinverse
  ```

- IAM PostgreSQL tokens are generated anew for each connection. Expired workshop
  credentials also prevent S3 uploads and future database connections. The current
  web EC2 instance has no IAM instance profile; a resource owner can later provide
  an EC2 role with S3 and `rds-db:connect` access for unattended AWS storage. Once
  that role is attached, remove the three static temporary credentials and any
  `AWS_PROFILE` setting from the server environment, then restart.
- Drafts, encounters, sources, portraits, feedback and reports live in
  `/var/lib/twinverse/twinverse.sqlite3`. Approved profiles also go to PostgreSQL
  and files to S3. Releases do not erase this workspace. The pre-existing EC2
  SQLite database is copied on the first installation only.
- Each deployment takes a SQLite backup under `/var/backups/twinverse/` and keeps
  ten backups. Recent application releases are retained under
  `/opt/twinverse/releases/`; `/opt/twinverse/current` selects the active one.
- These backups are on the EC2 volume. They do not protect against deleting the
  volume/workshop account; download an approved backup if you need to retain the
  demo after the event. Cloud records are historical copies; the app does not
  automatically restore its local workspace from them.

## HTTPS and instance changes

- Nginx exposes ports 80/443 and proxies to Python on `127.0.0.1:8000`.
  HTTP redirects to HTTPS; the backend validates the configured public origin
  and uses secure session cookies. Secrets/configuration are never served as
  static files.
- A trusted Let's Encrypt IP-address certificate is renewed automatically by
  `twinverse-certbot.timer`, with an Nginx reload after successful renewal.
  IP certificates are short-lived; renewal checks run twice daily.
  [Let's Encrypt IP certificate setup](https://letsencrypt.org/2026/03/11/shorter-certs-certbot.html)
- The current public IP can change if the instance is stopped/started unless
  the account owner associates a stable address. If it changes, update
  `TWINVERSE_PUBLIC_ORIGIN`, rerun the installer with the new IP, and use the
  new HTTPS address. No extra AWS instance/address was provisioned by this setup.
- Changes to the deployment controller, systemd units, or Nginx/HTTPS setup need
  an installer update on EC2; ordinary app changes deploy automatically.

## Recreate the setup on a provisioned Ubuntu instance

- The owner must provide SSH/sudo access and existing inbound ports 80/443.
  The installer uses the existing host; it does not create AWS infrastructure,
  IAM roles, users in PostgreSQL, or security-group rules.
- Create a private environment file using `.env.example`, and set:

  ```dotenv
  TWINVERSE_PUBLIC_ORIGIN=https://YOUR_PUBLIC_IP
  TWINVERSE_DB_PATH=/var/lib/twinverse/twinverse.sqlite3
  TWINVERSE_FACULTY_PASSWORD=YOUR_PRIVATE_PASSWORD
  TWINVERSE_DEVELOPER_PASSWORD=YOUR_PRIVATE_PASSWORD
  AWS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
  PGSSLROOTCERT=/etc/ssl/certs/ca-certificates.crt
  ```

  Use the appropriate database CA bundle if your endpoint requires a different
  trust chain. Preserve the other S3/database settings and credentials you use.
- Copy the repository's `deploy/` directory and the private environment file to
  the instance over SSH, then run:

  ```bash
  sudo bash deploy/bootstrap-ubuntu.sh YOUR_PUBLIC_IP PRIVATE_ENV MachaaX/twinverse-app
  ```

- Push the configuration/app code to GitHub. The initial deployment waits for a
  successful `main` push run of `.github/workflows/ci.yml`, just like later updates.

## Roll back manually

- Pause updates and deploy an older full commit SHA that passed CI on `main`:

  ```bash
  sudo systemctl stop twinverse-deploy.timer
  sudo python3 /usr/local/lib/twinverse/deploy.py --sha FULL_PREVIOUS_COMMIT_SHA
  ```

- Resume automatic deployment when ready:

  ```bash
  sudo systemctl start twinverse-deploy.timer
  ```

- A code rollback reuses the current SQLite data. If a future change performs an
  incompatible data migration, restoring a chosen backup is a separate operation;
  stop the app and inspect newer records before restoring it.
