# ✈️ Flight Alert Discord Bot

A Discord bot that tracks flight prices and alerts you when they drop.

## Features

- Track multiple flight routes per user
- Set target prices for alerts
- Automatic price checks on a schedule
- Get pinged when prices drop >5% or hit your target
- SQLite database for persistent storage

## Commands

| Command | Description | Example |
|---------|-------------|---------|
| `!track <origin> <dest> <date> [max_price]` | Start tracking a flight | `!track JFK LAX 2025-03-15 300` |
| `!list` | Show your active alerts | `!list` |
| `!check` | Manually check all your prices | `!check` |
| `!remove <id>` | Remove an alert | `!remove 3` |
| `!flighthelp` | Show help | `!flighthelp` |

## Setup

### 1. Create a Discord Bot

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application" → name it → Create
3. Go to "Bot" in the sidebar
4. Click "Reset Token" and copy your token (save it!)
5. Enable these Privileged Gateway Intents:
   - MESSAGE CONTENT INTENT ✅
6. Go to "OAuth2" → "URL Generator"
   - Scopes: `bot`
   - Bot Permissions: `Send Messages`, `Embed Links`, `Read Message History`
7. Copy the generated URL and open it to invite the bot to your server

### 2. Get Amadeus API Credentials

You should already have these. You need both:
- API Key
- API Secret

### 3. Deploy

#### Option A: Railway (Recommended - Free Tier)

1. Push this code to a GitHub repository
2. Go to [railway.app](https://railway.app) and sign in with GitHub
3. Click "New Project" → "Deploy from GitHub repo"
4. Select your repository
5. Add environment variables in Railway dashboard:
   - `DISCORD_TOKEN`
   - `AMADEUS_API_KEY`
   - `AMADEUS_API_SECRET`
   - `CHECK_INTERVAL_MINUTES` (optional, default 60)
6. Railway will auto-deploy!

#### Option B: Render (Free Tier)

1. Push code to GitHub
2. Go to [render.com](https://render.com)
3. New → Web Service → Connect your repo
4. Environment: Docker
5. Add environment variables
6. Deploy

#### Option C: Fly.io (Free Tier)

1. Install flyctl: `curl -L https://fly.io/install.sh | sh`
2. Login: `fly auth login`
3. Launch: `fly launch`
4. Set secrets:
   ```bash
   fly secrets set DISCORD_TOKEN=xxx
   fly secrets set AMADEUS_API_KEY=xxx
   fly secrets set AMADEUS_API_SECRET=xxx
   ```
5. Deploy: `fly deploy`

#### Option D: Run Locally (Testing)

```bash
# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env
# Edit .env with your credentials

# Run
python bot.py
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DISCORD_TOKEN` | Yes | Your Discord bot token |
| `AMADEUS_API_KEY` | Yes | Amadeus API key |
| `AMADEUS_API_SECRET` | Yes | Amadeus API secret |
| `CHECK_INTERVAL_MINUTES` | No | How often to check prices (default: 60) |

## Notes

- Uses 3-letter IATA airport codes (JFK, LAX, LHR, CDG, etc.)
- Dates must be in YYYY-MM-DD format
- Amadeus free tier has rate limits (~2000 calls/month)
- Bot alerts when:
  - Price drops below your max_price target
  - Price drops more than 5% since last check

## Troubleshooting

**Bot not responding?**
- Make sure MESSAGE CONTENT INTENT is enabled in Discord Developer Portal
- Check that bot has permissions to read/send in the channel

**No price data?**
- Verify your Amadeus credentials are correct
- Check if the airport codes are valid
- Amadeus may not have data for all routes

**Rate limited?**
- Increase `CHECK_INTERVAL_MINUTES` 
- Reduce number of tracked flights
