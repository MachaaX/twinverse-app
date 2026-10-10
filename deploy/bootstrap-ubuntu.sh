#!/usr/bin/env bash
# Run on Ubuntu 24.04: sudo bash deploy/bootstrap-ubuntu.sh PUBLIC_IP PRIVATE_ENV [OWNER/REPO]
set -euo pipefail
[[ $(id -u) -eq 0 ]] || { echo 'Run this installer with sudo.'; exit 1; }
public_ip=${1:?Pass the EC2 public IPv4 address}
private_env=${2:?Pass the private hosted environment file}
repository=${3:-MachaaX/twinverse-app}
script_dir=$(cd -- "$(dirname -- "$0")" && pwd)
python3 - "$public_ip" "$repository" <<'PY'
import ipaddress, re, sys
assert ipaddress.ip_address(sys.argv[1]).version == 4, 'An IPv4 address is required.'
assert re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', sys.argv[2]), 'Use owner/repository.'
PY
[[ -f "$private_env" ]] || { echo 'The private environment file is missing.'; exit 1; }

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3-venv git nginx nodejs curl ca-certificates >/tmp/twinverse-apt-install.log
id twinverse >/dev/null 2>&1 || useradd --system --create-home --home-dir /var/lib/twinverse --shell /usr/sbin/nologin twinverse
id twinverse-build >/dev/null 2>&1 || useradd --system --create-home --home-dir /var/lib/twinverse-build --shell /usr/sbin/nologin twinverse-build
install -d -m 755 /opt/twinverse /opt/twinverse/releases /usr/local/lib/twinverse /var/lib/twinverse-deploy
install -d -m 700 /etc/twinverse /var/backups/twinverse
install -d -o twinverse -g twinverse -m 700 /var/lib/twinverse
install -d -m 755 /var/www/twinverse-acme/.well-known/acme-challenge
if [[ -f /etc/twinverse/app.env ]]; then
    cp -p /etc/twinverse/app.env "/etc/twinverse/app.env.backup-$(date -u +%Y%m%dT%H%M%SZ)"
fi
install -o root -g root -m 600 "$private_env" /etc/twinverse/app.env
python3 - "$repository" <<'PY'
import json, sys
from pathlib import Path
Path('/etc/twinverse/deploy.json').write_text(json.dumps({'repository':sys.argv[1], 'branch':'main'})+'\n')
PY
install -o root -g root -m 644 "$script_dir/deploy.py" /usr/local/lib/twinverse/deploy.py
for unit in twinverse.service twinverse-deploy.service twinverse-deploy.timer twinverse-certbot.service twinverse-certbot.timer; do
    install -o root -g root -m 644 "$script_dir/$unit" "/etc/systemd/system/$unit"
done

# Preserve an existing EC2 workspace on the first installation. Later releases
# reuse the same database instead of copying or resetting it.
python3 - <<'PY'
import os, pwd, sqlite3
from pathlib import Path
source=Path('/home/ubuntu/twinverse-app/data/twinverse.sqlite3')
target=Path('/var/lib/twinverse/twinverse.sqlite3')
if source.is_file() and not target.exists():
    with sqlite3.connect(source) as old, sqlite3.connect(target) as new:
        old.backup(new)
    account=pwd.getpwnam('twinverse')
    os.chown(target, account.pw_uid, account.pw_gid)
    target.chmod(0o600)
    print('Preserved the existing EC2 SQLite workspace.')
PY

# Install a dedicated site without deleting the existing Nginx configuration.
cat > /etc/nginx/sites-available/twinverse <<NGINX
server {
    listen 80;
    server_name $public_ip;
    location /.well-known/acme-challenge/ { root /var/www/twinverse-acme; }
    location / { return 503; }
}
NGINX
ln -sfn /etc/nginx/sites-available/twinverse /etc/nginx/sites-enabled/twinverse
nginx -t
systemctl enable --now nginx
systemctl reload nginx

# Certbot >=5.4 supports trusted IP-address certificates with webroot validation.
# It is isolated from both Ubuntu packages and application dependencies.
python3 -m venv /opt/twinverse-certbot
/opt/twinverse-certbot/bin/python -m pip install --disable-pip-version-check 'certbot>=5.4,<6' >/tmp/twinverse-certbot-install.log
/opt/twinverse-certbot/bin/certbot certonly \
    --non-interactive --agree-tos --register-unsafely-without-email \
    --preferred-profile shortlived --webroot --webroot-path /var/www/twinverse-acme \
    --ip-address "$public_ip" --cert-name "twinverse-$public_ip" \
    --deploy-hook 'systemctl reload nginx'

cat > /etc/nginx/sites-available/twinverse <<NGINX
server {
    listen 80;
    server_name $public_ip;
    location /.well-known/acme-challenge/ { root /var/www/twinverse-acme; }
    location / { return 308 https://$public_ip\$request_uri; }
}
server {
    listen 443 ssl;
    server_name $public_ip;
    ssl_certificate /etc/letsencrypt/live/twinverse-$public_ip/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/twinverse-$public_ip/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    client_max_body_size 35m;
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host \$http_host;
        proxy_set_header X-Forwarded-Proto https;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }
}
NGINX
nginx -t
systemctl reload nginx
systemctl daemon-reload
systemctl enable twinverse.service
systemctl enable --now twinverse-certbot.timer twinverse-deploy.timer
systemctl start --no-block twinverse-deploy.service
echo "Configured hosting at https://$public_ip. The deployment waits for successful GitHub CI."
