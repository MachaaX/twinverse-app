# Existing Aurora database outage — 11 October 2026

## Current state

**The live demo is restored at `https://patientzero.me`.** With the user's
authorization to migrate, the app now uses PostgreSQL 16 on the existing EC2
instance. The Aurora gateway still fails TLS; the original cluster remains
intact. See [DEMO_DATABASE_SETUP.md](DEMO_DATABASE_SETUP.md) for the replacement
configuration, recovered data, backups and verification.

Before migration, Nginx and the application were running and HTTP health returned
200, while database-backed session requests returned 503. HTTP health alone does
not verify PostgreSQL connectivity.

## Evidence for the workshop organizer / AWS support

- AWS account: `454105254021`; region: `us-west-2`.
- Existing Aurora PostgreSQL cluster: `database-1`; instance:
  `database-1-instance-1`; engine: PostgreSQL 17.9.
- Writer hostname:
  `database-1.cluster-c5sig0eiuu7v.us-west-2.rds.amazonaws.com`.
- The Express cluster has its managed internet access gateway enabled and is
  reported as `available`.
- From EC2, all three resolved gateway addresses accept TCP on 5432 and reply
  `S` to PostgreSQL's SSL request, but the subsequent TLS handshake times out:
  `44.225.103.178`, `44.245.30.107`, and `54.201.252.93`.
- A separate workshop CodeEditor host also failed the TLS handshake on all
  three addresses. Writer-instance and reader-cluster hostname probes fail too.
- TLS 1.2 did not fix the problem. Direct TLS negotiation is unsupported by this
  gateway and returns a protocol error. Certificate verification remains enabled.
- Valid EC2 workshop credentials were restored after their absence was detected.
  AWS STS identity verification and fresh RDS IAM-token generation now succeed.
  Gateway TLS failure occurs before database authentication.

## Repairs completed without replacing the database

- Disabled auto-pause on the existing cluster: minimum 0.5 ACU, maximum 16 ACU.
  This retains nonzero compute capacity and incurs its normal running charges.
- Rebooted the existing writer, then stopped and started the existing cluster.
  AWS events confirm cluster stopped at 16:09:02 UTC and started at 16:15:10 UTC.
  TLS connectivity still fails after the completed restart.
- Applied a reversible EC2 connection-pool hotfix: preserve healthy connections
  for up to one hour and restart bounded background recovery cycles after a
  prolonged reconnect failure. SQL transactions are never replayed.
- Restored valid AWS credentials to root-only `/etc/twinverse/app.env` (0600).
  Original source/configuration backups remain root-only under
  `/var/backups/twinverse/`.
- Verified the hotfix with 153 backend tests (one skipped), frontend render and
  asynchronous privacy checks, and actual local PostgreSQL tests including
  recovery after repeated exhausted reconnect windows without a new request.

Those initial repairs did not create a new database or reset existing tables.
After the user authorized migration, a loopback-only PostgreSQL database was
created on the same EC2 server and restored from the verified recovery backup.
Current SQLite workspace data and existing S3 objects were preserved. Recovery
source and documentation are included in the subsequent authorized release;
backups and credentials remain private on EC2.

## Required next step

The workshop organizer / AWS support needs to investigate routing from this
cluster's managed Aurora Express internet gateway to its database instance.
Share the metadata and handshake evidence above, without sharing credentials.
The demonstration no longer depends on that gateway. Do not switch back merely
because AWS reports the cluster as available: first verify TLS, recover any
post-backup changes, reconcile new demo records and test account/encounter flows.
