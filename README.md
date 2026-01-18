# ✈️ TrackRoth

Flight price tracking with web dashboard + Discord bot.

## Features

- **Web App**: Landing page, Google/email login, dashboard
- **Discord Bot**: Track flights with `!track JFK LAX 2026-03-15`
- **Shared Database**: Alerts sync between web and Discord
- **Email + Discord Alerts**: Get notified on price drops

## Tech Stack

- Next.js 14 (web)
- Python Discord.py (bot)
- PostgreSQL (shared database)
- Prisma ORM
- SerpApi (Google Flights data)
- Resend (emails)

## Project Structure

```
/trackroth
  /bot                 # Discord bot (Python)
    bot.py
    Dockerfile
    requirements.txt
  /pages               # Next.js web app
  /lib                 # Shared utilities
  /prisma              # Database schema
```

## Deploy to Railway

You'll deploy **2 services** from the same repo:

### 1. Create Railway Project

1. Go to [railway.app](https://railway.app)
2. New Project → Deploy from GitHub repo

### 2. Add PostgreSQL Database

1. Click "New" → "Database" → "PostgreSQL"
2. Railway sets `DATABASE_URL` automatically

### 3. Deploy Web App (Service 1)

Railway auto-detects Next.js and deploys it. Set these variables:

```
NEXTAUTH_URL=https://your-web-app.railway.app
NEXTAUTH_SECRET=<random-32-char-string>

GOOGLE_CLIENT_ID=<from-google-cloud-console>
GOOGLE_CLIENT_SECRET=<from-google-cloud-console>

EMAIL_SERVER_HOST=smtp.resend.com
EMAIL_SERVER_PORT=465
EMAIL_SERVER_USER=resend
EMAIL_SERVER_PASSWORD=<your-resend-api-key>
EMAIL_FROM=TrackRoth <noreply@yourdomain.com>

RESEND_API_KEY=<your-resend-api-key>
SERPAPI_KEY=<your-serpapi-key>
CRON_SECRET=<random-string>
```

### 4. Deploy Discord Bot (Service 2)

1. In Railway, click "New" → "GitHub Repo" (same repo)
2. Go to Settings → change **Root Directory** to `/bot`
3. Set these variables:

```
DISCORD_TOKEN=<your-discord-bot-token>
SERPAPI_KEY=<your-serpapi-key>
DATABASE_URL=<copy-from-postgres-service>
CHECK_INTERVAL_MINUTES=360
```

**Important:** Copy the `DATABASE_URL` from the PostgreSQL service so the bot shares the same database.

### 5. Run Database Migration

In Railway terminal (web service):

```bash
npx prisma db push
```

### 6. Setup External Services

**Google OAuth:**
1. [Google Cloud Console](https://console.cloud.google.com) → Create project
2. APIs & Services → Credentials → OAuth 2.0 Client
3. Add redirect: `https://your-app.railway.app/api/auth/callback/google`

**Resend (emails):**
1. Sign up at [resend.com](https://resend.com)
2. Get API key, optionally add custom domain

**Discord Bot:**
1. [Discord Developer Portal](https://discord.com/developers/applications)
2. Create app → Bot → Get token
3. Enable MESSAGE CONTENT INTENT
4. Invite to server with OAuth2 URL Generator

### 7. Setup Cron for Price Checking

The web app needs a cron job to check prices. Use [cron-job.org](https://cron-job.org):

- URL: `https://your-app.railway.app/api/cron/check-prices`
- Header: `Authorization: Bearer YOUR_CRON_SECRET`
- Schedule: Every 6 hours

(The Discord bot runs its own background loop, so this cron is just for email alerts)

## Discord Commands

| Command | Description |
|---------|-------------|
| `!track JFK LAX 2026-03-15` | Track a flight |
| `!track JFK LAX 2026-03-15 300` | Track with target price |
| `!list` | Show your alerts |
| `!check` | Check prices now |
| `!remove <id>` | Remove an alert |
| `!flighthelp` | Show help |

## How It Works

1. Users create alerts via web or Discord
2. Both write to the same PostgreSQL database
3. Price checker runs every 6 hours
4. Web users get email alerts
5. Discord users get DM alerts

## API Limits

- SerpApi free tier: 250 searches/month
- At 6-hour intervals: ~120 checks/alert/month
- Budget for ~2 alerts on free tier

## Local Development

```bash
# Install web dependencies
npm install

# Setup database
npx prisma db push

# Run web dev server
npm run dev

# Run Discord bot (separate terminal)
cd bot
pip install -r requirements.txt
python bot.py
```

