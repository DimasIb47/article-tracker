# VPS Setup Guide — GitHub + Docker

## 1. Setup VPS (one-time)

```bash
ssh root@YOUR_VPS_IP

# Update & install Docker
apt update && apt upgrade -y
curl -fsSL https://get.docker.com | sh
apt install docker-compose-plugin git -y

# Open dashboard port
ufw allow 22/tcp
ufw allow 8080/tcp
ufw enable
```

## 2. Clone & Configure

```bash
cd /root
git clone https://github.com/DimasIb47/article-tracker.git
cd article-tracker

# Create .env from template
cp .env.example .env
nano .env   # Fill in your real values
```

## 3. Start

```bash
docker compose up -d
```

## 4. Verify

```bash
# Check all containers running
docker compose ps

# Check bot logs
docker compose logs -f bot

# Open dashboard
# http://YOUR_VPS_IP:8080?key=YOUR_PASSWORD
```

## Update (after git push)

```bash
ssh root@YOUR_VPS_IP
cd /root/article-tracker
git pull
docker compose up -d --build
```

## Quick Commands

| Command | What |
|---|---|
| `docker compose up -d` | Start all |
| `docker compose down` | Stop all |
| `docker compose restart bot` | Restart bot |
| `docker compose logs -f bot` | Bot logs |
| `docker compose logs -f dashboard` | Dashboard logs |
| `docker compose ps` | Status |
| `git pull && docker compose up -d --build` | Update from GitHub |
