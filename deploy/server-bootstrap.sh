#!/usr/bin/env bash
# CRUMBS — Ubuntu 22.04 VPS bootstrap
# Run as root on a fresh server: bash deploy/server-bootstrap.sh
set -euo pipefail

echo "==> Updating system packages..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get upgrade -y

echo "==> Installing base tools..."
apt-get install -y \
  ca-certificates \
  curl \
  gnupg \
  lsb-release \
  ufw \
  fail2ban \
  git \
  gettext-base

echo "==> Installing Docker..."
if ! command -v docker >/dev/null 2>&1; then
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
    $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi

systemctl enable docker
systemctl start docker

echo "==> Configuring firewall (UFW)..."
ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

echo "==> Enabling fail2ban..."
systemctl enable fail2ban
systemctl start fail2ban

echo "==> Creating deploy user (optional)..."
if ! id -u deploy >/dev/null 2>&1; then
  useradd -m -s /bin/bash deploy
  usermod -aG docker deploy
  echo "User 'deploy' created. Set password: passwd deploy"
fi

echo ""
echo "Bootstrap complete."
echo "Next steps:"
echo "  1. Clone repo to /opt/crumbs (or your path)"
echo "  2. cp .env.example .env && edit secrets + DOMAIN"
echo "  3. ./deploy/deploy.sh init"
echo "  4. ./deploy/init-ssl.sh"
