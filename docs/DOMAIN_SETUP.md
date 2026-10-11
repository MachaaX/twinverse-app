# patientzero.me and Google sign-in

The public address is `https://patientzero.me`. The existing EC2 address is
`44.246.200.136`. The domain uses Namecheap BasicDNS; purchasing hosting or a paid
SSL certificate is not required for this EC2 setup.

EC2 was configured on October 10, 2026: trusted HTTPS is active for the root
domain and `www`, the old IP and `www` redirect to the root domain, and the app's
public origin and Google callback use the root domain. The certificate expires
January 9, 2027 and automatic certificate renewal passed its rehearsal. The
Google callback is registered: an anonymous browser reaches Google's sign-in
page without `redirect_uri_mismatch` or `invalid_client`. Completing account
signup or login still requires the user's interactive Google sign-in.

## Namecheap

1. Open **Domain List → patientzero.me → Manage → Advanced DNS**.
2. Replace the four existing `@` A records pointing to `185.199.108.153`,
   `185.199.109.153`, `185.199.110.153`, and `185.199.111.153` with one record:

   | Type | Host | Value | TTL |
   | --- | --- | --- | --- |
   | A Record | `@` | `44.246.200.136` | Automatic |
   | CNAME Record | `www` | `patientzero.me` | Automatic or existing 30 min |

3. Keep the existing `www` CNAME and all email/TXT records. Keep Namecheap
   BasicDNS nameservers. Save changes using the green checkmark.
4. Check authoritative DNS and a public resolver before requesting a certificate:

   ```bash
   dig @dns1.registrar-servers.com patientzero.me A +short
   dig @dns2.registrar-servers.com patientzero.me A +short
   dig @1.1.1.1 patientzero.me A +short
   ```

   Each should return only `44.246.200.136`; cached answers can take longer to
   update. See [Namecheap's A record instructions](https://www.namecheap.com/support/knowledgebase/article.aspx/319/2237/how-can-i-set-up-an-a-address-record-for-my-domain/).

## EC2 HTTPS and app configuration

- The prepared HTTP virtual host for both names serves the ACME challenge from
  `/var/www/twinverse-acme`. Keep ports 80 and 443 reachable for issuance and
  automatic renewal.
- Once DNS points to EC2, issue the certificate on EC2:

  ```bash
  sudo /opt/twinverse-certbot/bin/certbot certonly \
    --non-interactive --agree-tos --register-unsafely-without-email \
    --webroot --webroot-path /var/www/twinverse-acme \
    --cert-name patientzero.me -d patientzero.me -d www.patientzero.me \
    --deploy-hook 'systemctl reload nginx'
  ```

- Configure Nginx to proxy HTTPS `patientzero.me` to `127.0.0.1:8000`, forwarding
  the original Host and `X-Forwarded-Proto: https`. Preserve the 35 MB request
  limit and 300-second proxy timeouts. Redirect HTTP, `www`, and the old IP URL
  to `https://patientzero.me`, while preserving HTTP ACME challenge routes.
- Set only these public values in root-only `/etc/twinverse/app.env`; keep all
  existing credentials and database settings:

  ```dotenv
  TWINVERSE_PUBLIC_ORIGIN=https://patientzero.me
  TWINVERSE_GOOGLE_REDIRECT_URI=https://patientzero.me/api/auth/google/callback
  ```

- Check `sudo nginx -t`, restart `twinverse`, and reload Nginx. The existing
  `twinverse-certbot.timer` renews both certificates and reloads Nginx. Root
  configuration stays outside application releases, so continuous deployment
  preserves it.
- Verify `https://patientzero.me/api/health`, HTTP/`www` redirects, and
  `/api/auth/config`. Sign in again on the new domain; browser cookies from the
  old IP address do not transfer. Existing accounts and history stay in their
  databases.
- If EC2 is stopped and started, an ordinary public IP may change. An AWS
  account owner can associate an Elastic IP for a stable address; if the address
  changes, update the `@` A record. No new AWS address is allocated by this setup.

## Google Auth Platform

1. Open [Google Auth Platform → Clients](https://console.cloud.google.com/auth/clients)
   in the Google Cloud project that owns the existing Web application client.
2. Select the client whose ID ends in
   `0otsc4rnipqofbj8ls5a1i9fm2uv3ign.apps.googleusercontent.com`.
3. Under **Authorized redirect URIs**, add exactly:

   ```text
   https://patientzero.me/api/auth/google/callback
   ```

   Preserve the local callback `http://127.0.0.1:8000/api/auth/google/callback`.
   Save the client. Do not append `#login`, a trailing slash, or `www` to the
   production callback. Google requires an exact match. This server-side flow
   does not require an Authorized JavaScript origin. See [Google's web-server
   OAuth documentation](https://developers.google.com/identity/protocols/oauth2/web-server).
4. Under **Branding**, use `patientzero.me` as an Authorized domain if requested.
   Use `https://patientzero.me` for the application homepage. Complete domain
   ownership verification if Google requests it.
5. Under **Audience**, a Testing app permits only its test users. Add the Google
   accounts that should test it. To make Google sign-in available to the public,
   publish the app to Production and complete any requirements Google presents.
6. Open `https://patientzero.me/#signup`, select Medical student or Faculty,
   and choose **Continue with Google**. After registering, test login and logout
   at `https://patientzero.me/#login`. An existing password account can use
   **Link Google** after signing in to connect the matching Google email.

The Google client secret remains in private environment files on EC2 and local
development machines. It must never be copied into browser code or Git.
