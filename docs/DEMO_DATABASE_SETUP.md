# Restored demo database — 11 October 2026

The public site is running at **https://patientzero.me**. Account and approved
patient storage now use PostgreSQL 16 on the existing EC2 instance; they no longer
depend on the broken Aurora Express TLS gateway. No new RDS cluster was created,
and the original Aurora database is intact. The recovery release includes the
connection-pool fix, backup source/service definitions and team guide; private
server configuration and recovered database contents stay outside Git.

## Current storage

| Storage | Responsibility |
| --- | --- |
| PostgreSQL 16 on EC2 | Accounts/profiles, session hashes, OAuth state, approved patient versions, speech metadata |
| `/var/lib/twinverse/twinverse.sqlite3` | Cases/drafts, encounters/transcripts, reviews, feedback, attachment copies, reply cache, speech outbox |
| Private S3 `twinverse-s3-bucket-1` | Published patient documents and optional audio recordings |

PostgreSQL listens only on `127.0.0.1:5432`; no public database port or security
group was added. Database `twinverse_demo_20261011` uses the restricted role
`twinverse_demo_app`. The app uses password authentication, `sslmode=verify-full`
and an explicitly trusted local TLS certificate. The application role cannot
create databases/roles and is not a superuser.

Private connection configuration remains root-only in `/etc/twinverse/app.env`
and `/etc/twinverse/demo-postgres.env`. Do not print, commit or include those
files in presentation material. The service dependency is
`/etc/systemd/system/twinverse.service.d/demo-postgres.conf`.

## Recovered data and limits

- All seven PostgreSQL tables were restored from the last verified readable
  Aurora backup. Original rows were checked against the source before reconciling
  newer EC2 workspace records.
- Nine users, five faculty profiles and four medical-student profiles were
  preserved, including IDs, password hashes, Google identities and roles.
- Reconciliation recovered ten approved versions and 35 speech-clip records.
  All 35 audio jobs are now ready; no deletion request is pending.
- The latest EC2 workspace was retained: 27 cases, 96 encounters, 47 attachments
  and 133 reply-cache records at cutover. Every encounter owner matched a
  recovered user.
- Old backed-up sessions/OAuth states were invalidated so previously revoked
  sessions or consumed login states are not resurrected. Users must sign in again.
- Aurora-only changes after the last readable backup may be unavailable. The
  original cluster remains preserved for later reconciliation.

## Verification completed

- Live signup, login, logout, persisted session and concurrent session requests.
- Faculty approval writing PostgreSQL version/manifest and an S3 TXT document.
- Student encounter creation, saved turns, attachment retrieval and ownership
  isolation; another student cannot access the encounter.
- Optional audio upload, PostgreSQL metadata, S3 playback with byte comparison
  and deletion, plus completion and student/faculty encounter history.
- Seven-domain assessment evidence, real Sonnet 5 invocation, and Google OAuth
  start/state with the production callback. Interactive Google consent was not
  re-completed during this recovery verification.
- A fresh backup was actually restored into a temporary database on EC2. All
  seven tables restored; persistent row contents matched the live database.
  Backup hashes and SQLite integrity/counts passed. The temporary database was
  removed afterward; synthetic workflow test records were cleaned up.

## Backups and maintenance

`twinverse-demo-backup.timer` runs every 15 minutes and retains 24 root-only
snapshots in `/var/backups/twinverse/demo-auto/`. Each snapshot contains
`demo-postgres.pgdump`, `workspace.sqlite3`, and a checksum/count manifest.
The dump does not contain the plaintext database role password. S3 raw recordings
are not duplicated in this backup; attachment copies remain in the workspace.

Original migration/cutover backups and old environment configuration also remain
under `/var/backups/twinverse/`, readable only by root. Sensitive backups were
kept on EC2; no new local/off-site export was performed.

Useful checks on EC2:

```bash
sudo systemctl is-active twinverse postgresql@16-main nginx twinverse-demo-backup.timer
sudo systemctl start twinverse-demo-backup.service
sudo journalctl -u twinverse-demo-backup -n 10 --no-pager
cd /opt/twinverse/current
sudo env TWINVERSE_ENV_FILE=/etc/twinverse/app.env .venv/bin/python -m backend.cloud_storage check
```

Also sign in to the actual site and use **Generate patients → Test connection**.
`/api/health` checks the running application and release, not database or model
access. Inspect logs privately; do not paste credentials or transcripts.

The existing deploy timer still follows eligible `main` revisions. The
connection-pool fix is included in this recovery release. The database
environment and systemd dependency sit outside release directories.

Non-secret operational sources are versioned under `deploy/`: `demo_backup.py`,
`twinverse-demo-backup.service`, `twinverse-demo-backup.timer` and
`demo-postgres.conf`. They correspond to the installed configuration above.
Normal app deployments do not reinstall system services or change database
credentials. If rebuilding this host, first install PostgreSQL 16, create and
restore the database, and configure verified loopback TLS/private credentials.
Only then install the backup and dependency definitions:

```bash
sudo install -d /usr/local/lib/twinverse /etc/systemd/system/twinverse.service.d
sudo install -m 0755 deploy/demo_backup.py /usr/local/lib/twinverse/backup-demo.py
sudo install -m 0644 deploy/twinverse-demo-backup.service deploy/twinverse-demo-backup.timer /etc/systemd/system/
sudo install -m 0644 deploy/demo-postgres.conf /etc/systemd/system/twinverse.service.d/demo-postgres.conf
sudo systemctl daemon-reload
sudo systemctl enable --now twinverse-demo-backup.timer
```

## Lifecycle and rollback

This repair removes the Aurora gateway/IAM database-authentication dependency.
EC2, its disk, S3 and Bedrock still belong to a temporary workshop account. Local
disk backups do not protect against workshop teardown or volume deletion. A
permanent account or an explicitly approved off-site recovery copy is needed for
longer-term survival.

Do not revert to the preserved Aurora configuration until its TLS gateway is
healthy and post-cutover changes have been reconciled. Never restore an older
SQLite workspace over the current one merely to match an older Aurora dump.
Take a fresh consistent backup and validate a candidate restore before any
cutover. Keep the existing databases and backups until recovery is confirmed.
