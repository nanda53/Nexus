#!/bin/bash
# Paste this into EC2 > Launch instance > Advanced details > User data
# (Amazon Linux 2023, t3.small, security group allowing HTTP 80).
# EDIT THE 3 LINES BELOW FIRST.
REPO_URL="https://github.com/YOUR_USER/YOUR_REPO.git"
DB_PASSWORD="ChangeThisPassword123"
SECRET_KEY="change-this-to-a-long-random-string-0123456789abcdef"

set -ex
dnf install -y docker git
systemctl enable --now docker
mkdir -p /usr/local/lib/docker/cli-plugins
curl -SL https://github.com/docker/compose/releases/download/v2.29.7/docker-compose-linux-x86_64 \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
git clone "$REPO_URL" /opt/nexus
cd /opt/nexus
printf 'DB_PASSWORD=%s\nSECRET_KEY=%s\n' "$DB_PASSWORD" "$SECRET_KEY" > .env
docker compose -f docker-compose.prod.yml up -d --build
