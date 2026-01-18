import discord
from discord.ext import commands, tasks
import os
import requests
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse

# Configuration
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
CHECK_INTERVAL_MINUTES = int(os.getenv("CHECK_INTERVAL_MINUTES", 360))

# Parse database URL
db_url = urlparse(DATABASE_URL)

def get_db():
    return psycopg2.connect(
        host=db_url.hostname,
        port=db_url.port,
        user=db_url.username,
        password=db_url.password,
        database=db_url.path[1:],
        cursor_factory=RealDictCursor
    )

# Initialize Discord bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

def get_or_create_user(discord_id, discord_name):
    """Get or create a user by Discord ID."""
    conn = get_db()
    cursor = conn.cursor()
    
    # Check if user exists with this discord ID in name field (we'll use name to store discord_id)
    cursor.execute(
        'SELECT * FROM "User" WHERE name = %s',
        (f"discord:{discord_id}",)
    )
    user = cursor.fetchone()
    
    if not user:
        # Create new user
        import uuid
        user_id = str(uuid.uuid4())[:25]  # cuid-like
        cursor.execute(
            'INSERT INTO "User" (id, name, email) VALUES (%s, %s, %s) RETURNING *',
            (user_id, f"discord:{discord_id}", f"discord_{discord_id}@trackroth.local")
        )
        user = cursor.fetchone()
        conn.commit()
    
    conn.close()
    return user

def add_alert(user_id, origin, destination, departure_date, max_price=None):
    """Add a new flight alert."""
    conn = get_db()
    cursor = conn.cursor()
    
    import uuid
    alert_id = str(uuid.uuid4())[:25]
    
    cursor.execute('''
        INSERT INTO "Alert" (id, "userId", origin, destination, "departureDate", "maxPrice", "isActive", "createdAt", "updatedAt")
        VALUES (%s, %s, %s, %s, %s, %s, true, NOW(), NOW())
        RETURNING *
    ''', (alert_id, user_id, origin.upper(), destination.upper(), departure_date, max_price))
    
    alert = cursor.fetchone()
    conn.commit()
    conn.close()
    return alert

def get_user_alerts(user_id):
    """Get all active alerts for a user."""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM "Alert" 
        WHERE "userId" = %s AND "isActive" = true
        ORDER BY "createdAt" DESC
    ''', (user_id,))
    
    alerts = cursor.fetchall()
    conn.close()
    return alerts

def get_all_active_alerts():
    """Get all active alerts with user info."""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT a.*, u.name, u.email 
        FROM "Alert" a
        JOIN "User" u ON a."userId" = u.id
        WHERE a."isActive" = true AND a."departureDate" >= CURRENT_DATE
    ''')
    
    alerts = cursor.fetchall()
    conn.close()
    return alerts

def remove_alert(alert_id, user_id):
    """Deactivate an alert."""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE "Alert" SET "isActive" = false, "updatedAt" = NOW()
        WHERE id = %s AND "userId" = %s
    ''', (alert_id, user_id))
    
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def update_last_price(alert_id, price):
    """Update the last known price for an alert."""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE "Alert" SET "lastPrice" = %s, "updatedAt" = NOW()
        WHERE id = %s
    ''', (price, alert_id))
    
    # Also save to price history
    import uuid
    history_id = str(uuid.uuid4())[:25]
    cursor.execute('''
        INSERT INTO "PriceHistory" (id, "alertId", price, "checkedAt")
        VALUES (%s, %s, %s, NOW())
    ''', (history_id, alert_id, price))
    
    conn.commit()
    conn.close()

def get_flight_price(origin, destination, departure_date):
    """Fetch the cheapest flight price from Google Flights via SerpApi."""
    try:
        print(f"Searching flights: {origin} -> {destination} on {departure_date}", flush=True)
        
        params = {
            "engine": "google_flights",
            "departure_id": origin.upper(),
            "arrival_id": destination.upper(),
            "outbound_date": departure_date,
            "currency": "USD",
            "hl": "en",
            "type": "2",
            "api_key": SERPAPI_KEY
        }
        
        response = requests.get("https://serpapi.com/search", params=params)
        data = response.json()
        
        if "error" in data:
            print(f"SerpApi error: {data['error']}", flush=True)
            return None
        
        flights = data.get("best_flights", []) or data.get("other_flights", [])
        
        if flights and len(flights) > 0:
            price = flights[0].get("price")
            if price:
                print(f"Found price: ${price}", flush=True)
                return float(price)
        
        print("No flight data returned", flush=True)
        return None
        
    except Exception as e:
        print(f"Unexpected error: {type(e).__name__}: {e}", flush=True)
        return None

# Store channel IDs for Discord notifications
discord_channels = {}

@bot.event
async def on_ready():
    print(f"Bot is online as {bot.user}", flush=True)
    print(f"SerpApi Key loaded: {'Yes' if SERPAPI_KEY else 'NO - MISSING!'}", flush=True)
    print(f"Database connected: {'Yes' if DATABASE_URL else 'NO - MISSING!'}", flush=True)
    if not check_prices.is_running():
        check_prices.start()

@bot.command(name="track")
async def track_flight(ctx, origin: str, destination: str, departure_date: str, max_price: float = None):
    """Track a flight route."""
    print(f"=== TRACK COMMAND ===", flush=True)
    
    # Validate date
    try:
        parsed_date = datetime.strptime(departure_date, "%Y-%m-%d")
        if parsed_date.date() < datetime.now().date():
            await ctx.send("❌ Date must be in the future!")
            return
    except ValueError:
        await ctx.send("❌ Invalid date format. Use YYYY-MM-DD (e.g., 2026-03-15)")
        return
    
    if len(origin) != 3 or len(destination) != 3:
        await ctx.send("❌ Use 3-letter airport codes (e.g., JFK, LAX)")
        return
    
    # Get or create user
    user = get_or_create_user(ctx.author.id, str(ctx.author))
    
    # Store channel for notifications
    discord_channels[user['id']] = ctx.channel.id
    
    await ctx.send(f"🔍 Searching for flights {origin.upper()} → {destination.upper()}...")
    
    # Get current price
    current_price = get_flight_price(origin, destination, departure_date)
    
    # Create alert
    alert = add_alert(user['id'], origin, destination, departure_date, max_price)
    
    if current_price:
        update_last_price(alert['id'], current_price)
        price_msg = f"Current price: **${current_price:.2f}**"
    else:
        price_msg = "Could not fetch price (will retry later)"
    
    max_msg = f" | Target: ≤${max_price:.2f}" if max_price else ""
    
    await ctx.send(
        f"✅ Now tracking **{origin.upper()} → {destination.upper()}** on **{departure_date}**{max_msg}\n"
        f"{price_msg}\n"
        f"Alert ID: `{alert['id'][:8]}...`"
    )

@bot.command(name="list")
async def list_alerts(ctx):
    """List your flight alerts."""
    user = get_or_create_user(ctx.author.id, str(ctx.author))
    alerts = get_user_alerts(user['id'])
    
    if not alerts:
        await ctx.send("No active alerts. Use `!track` to add one!")
        return
    
    embed = discord.Embed(title="✈️ Your Flight Alerts", color=0x00aaff)
    
    for alert in alerts:
        date_str = alert['departureDate'].strftime("%Y-%m-%d")
        price_info = f"${alert['lastPrice']:.2f}" if alert['lastPrice'] else "Checking..."
        target = f" | Target: ${alert['maxPrice']:.2f}" if alert['maxPrice'] else ""
        
        embed.add_field(
            name=f"{alert['origin']} → {alert['destination']} on {date_str}",
            value=f"Price: {price_info}{target}\nID: `{alert['id'][:8]}...`",
            inline=False
        )
    
    await ctx.send(embed=embed)

@bot.command(name="remove")
async def remove_alert_cmd(ctx, alert_id: str):
    """Remove an alert by ID (first 8 chars)."""
    user = get_or_create_user(ctx.author.id, str(ctx.author))
    alerts = get_user_alerts(user['id'])
    
    # Find matching alert
    matching = [a for a in alerts if a['id'].startswith(alert_id)]
    
    if not matching:
        await ctx.send(f"❌ No alert found starting with `{alert_id}`")
        return
    
    if remove_alert(matching[0]['id'], user['id']):
        await ctx.send(f"✅ Alert removed!")
    else:
        await ctx.send(f"❌ Could not remove alert")

@bot.command(name="check")
async def check_now(ctx):
    """Manually check prices."""
    user = get_or_create_user(ctx.author.id, str(ctx.author))
    alerts = get_user_alerts(user['id'])
    
    if not alerts:
        await ctx.send("No alerts to check.")
        return
    
    await ctx.send("🔍 Checking prices...")
    
    for alert in alerts:
        date_str = alert['departureDate'].strftime("%Y-%m-%d")
        price = get_flight_price(alert['origin'], alert['destination'], date_str)
        
        if price:
            old_price = alert['lastPrice']
            update_last_price(alert['id'], price)
            
            change = ""
            if old_price:
                diff = price - old_price
                if diff < 0:
                    change = f" (📉 ${abs(diff):.2f} lower!)"
                elif diff > 0:
                    change = f" (📈 ${diff:.2f} higher)"
            
            await ctx.send(f"**{alert['origin']} → {alert['destination']}** ({date_str}): **${price:.2f}**{change}")
        else:
            await ctx.send(f"**{alert['origin']} → {alert['destination']}** ({date_str}): Could not fetch")

@bot.command(name="flighthelp")
async def flight_help(ctx):
    """Show help."""
    embed = discord.Embed(
        title="✈️ TrackRoth Bot",
        description="Track flight prices from Discord!",
        color=0x00aaff
    )
    
    embed.add_field(name="!track JFK LAX 2026-03-15 [max_price]", value="Track a flight", inline=False)
    embed.add_field(name="!list", value="Show your alerts", inline=False)
    embed.add_field(name="!check", value="Check prices now", inline=False)
    embed.add_field(name="!remove <id>", value="Remove an alert", inline=False)
    embed.add_field(name="🌐 Web Dashboard", value="Manage alerts at trackroth.com", inline=False)
    
    await ctx.send(embed=embed)

@tasks.loop(minutes=CHECK_INTERVAL_MINUTES)
async def check_prices():
    """Background price checker."""
    print("=== SCHEDULED PRICE CHECK ===", flush=True)
    
    alerts = get_all_active_alerts()
    
    for alert in alerts:
        date_str = alert['departureDate'].strftime("%Y-%m-%d")
        price = get_flight_price(alert['origin'], alert['destination'], date_str)
        
        if not price:
            continue
        
        should_notify = False
        reason = ""
        
        if alert['maxPrice'] and price <= alert['maxPrice']:
            should_notify = True
            reason = f"🎯 Hit your target of ${alert['maxPrice']:.2f}!"
        elif alert['lastPrice'] and price < alert['lastPrice'] * 0.95:
            should_notify = True
            drop = alert['lastPrice'] - price
            reason = f"📉 Dropped ${drop:.2f}!"
        
        update_last_price(alert['id'], price)
        
        if should_notify:
            # Try Discord notification if user is from Discord
            if alert['name'] and alert['name'].startswith('discord:'):
                discord_id = int(alert['name'].split(':')[1])
                try:
                    user = await bot.fetch_user(discord_id)
                    await user.send(
                        f"✈️ **Flight Alert!**\n"
                        f"**{alert['origin']} → {alert['destination']}** on **{date_str}**\n"
                        f"Price: **${price:.2f}**\n"
                        f"{reason}"
                    )
                except Exception as e:
                    print(f"Could not DM user: {e}", flush=True)

@check_prices.before_loop
async def before_check():
    await bot.wait_until_ready()

if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("Error: DISCORD_TOKEN not set", flush=True)
        exit(1)
    if not DATABASE_URL:
        print("Error: DATABASE_URL not set", flush=True)
        exit(1)
    
    bot.run(DISCORD_TOKEN)
