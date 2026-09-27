#!/bin/bash
# Installed by an administrator as /usr/local/sbin/lpk-deploy.
set -euo pipefail
exec 9>/var/lock/lpk-deploy.lock
flock 9
stage=$(mktemp -d /var/tmp/lpk-release.XXXXXX)
trap 'rm -rf "$stage"' EXIT
chown ubuntu:ubuntu "$stage"
runuser -u ubuntu -- tar -xzf - -C "$stage"
test -f "$stage/backend/server.py"
test -f "$stage/frontend/index.html"
rsync -a --exclude .venv --exclude .env "$stage/backend/" /var/www/lpk/backend/
/var/www/lpk/backend/.venv/bin/pip install -r /var/www/lpk/backend/requirements.txt
chown -R root:lpk /var/www/lpk/backend
chmod -R g+rX /var/www/lpk/backend
set -a
source /etc/lpk/backend.env
set +a
cd /var/www/lpk/backend
runuser -u lpk --preserve-environment -- .venv/bin/python seed_student_accounts.py
systemctl restart lpk
for attempt in {1..30}; do
    if curl -fsS http://127.0.0.1:8002/api/ >/dev/null; then
        rsync -a "$stage/frontend/" /var/www/lpk/frontend/
        chmod -R a+rX /var/www/lpk/frontend
        curl -fsS https://lpk.techworksnesia.com/api/
        exit 0
    fi
    sleep 2
done
journalctl -u lpk -n 30 --no-pager
exit 1
