import discord
from discord.ext import commands, tasks
import sqlite3
import os
import requests
from datetime import datetime

# Configuration
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
CHECK_INTERVAL_MINUTES = int(os.getenv("CHECK_INTERVAL_MINUTES", 360))  # Default 6 hours to conserve API calls

# Initialize Discord bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Database setup
def init_db():
    conn = sqlite3.connect("flight_alerts.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            channel_id INTEGER NOT NULL,
            origin TEXT NOT NULL,
            destination TEXT NOT NULL,
            departure_date TEXT NOT NULL,
            max_price REAL,
            last_price REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def add_alert(user_id, channel_id, origin, destination, departure_date, max_price=None):
    conn = sqlite3.connect("flight_alerts.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO alerts (user_id, channel_id, origin, destination, departure_date, max_price)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, channel_id, origin.upper(), destination.upper(), departure_date, max_price))
    conn.commit()
    alert_id = cursor.lastrowid
    conn.close()
    return alert_id

def get_user_alerts(user_id):
    conn = sqlite3.connect("flight_alerts.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM alerts WHERE user_id = ?", (user_id,))
    alerts = cursor.fetchall()
    conn.close()
    return alerts

def get_all_alerts():
    conn = sqlite3.connect("flight_alerts.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM alerts")
    alerts = cursor.fetchall()
    conn.close()
    return alerts

def remove_alert(alert_id, user_id):
    conn = sqlite3.connect("flight_alerts.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM alerts WHERE id = ? AND user_id = ?", (alert_id, user_id))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def update_last_price(alert_id, price):
    conn = sqlite3.connect("flight_alerts.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE alerts SET last_price = ? WHERE id = ?", (price, alert_id))
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
            "type": "2",  # One-way flight
            "api_key": SERPAPI_KEY
        }
        
        response = requests.get("https://serpapi.com/search", params=params)
        data = response.json()
        
        if "error" in data:
            print(f"SerpApi error: {data['error']}", flush=True)
            return None
        
        # Get best flights or other flights
        flights = data.get("best_flights", []) or data.get("other_flights", [])
        
        if flights and len(flights) > 0:
            # Get the cheapest price
            price = flights[0].get("price")
            if price:
                print(f"Found price: ${price}", flush=True)
                return float(price)
        
        print("No flight data returned", flush=True)
        return None
        
    except Exception as e:
        print(f"Unexpected error: {type(e).__name__}: {e}", flush=True)
        return None

@bot.event
async def on_ready():
    print(f"Bot is online as {bot.user}", flush=True)
    print(f"SerpApi Key loaded: {'Yes' if SERPAPI_KEY else 'NO - MISSING!'}", flush=True)
    print(f"Check interval: {CHECK_INTERVAL_MINUTES} minutes", flush=True)
    init_db()
    if not check_prices.is_running():
        check_prices.start()

@bot.command(name="track")
async def track_flight(ctx, origin: str, destination: str, departure_date: str, max_price: float = None):
    """
    Track a flight route.
    Usage: !track <origin> <destination> <YYYY-MM-DD> [max_price]
    Example: !track JFK LAX 2025-03-15 300
    """
    print(f"=== TRACK COMMAND RECEIVED ===", flush=True)
    print(f"User: {ctx.author}, Origin: {origin}, Dest: {destination}, Date: {departure_date}", flush=True)
    
    # Validate date format
    try:
        datetime.strptime(departure_date, "%Y-%m-%d")
    except ValueError:
        await ctx.send("❌ Invalid date format. Please use YYYY-MM-DD (e.g., 2025-03-15)")
        return
    
    # Validate airport codes (basic check)
    if len(origin) != 3 or len(destination) != 3:
        await ctx.send("❌ Please use 3-letter airport codes (e.g., JFK, LAX, LHR)")
        return
    
    # Check current price
    await ctx.send(f"🔍 Searching for flights {origin.upper()} → {destination.upper()}...")
    current_price = get_flight_price(origin.upper(), destination.upper(), departure_date)
    
    alert_id = add_alert(
        user_id=ctx.author.id,
        channel_id=ctx.channel.id,
        origin=origin,
        destination=destination,
        departure_date=departure_date,
        max_price=max_price
    )
    
    if current_price:
        update_last_price(alert_id, current_price)
        price_msg = f"Current cheapest price: **${current_price:.2f}**"
    else:
        price_msg = "Could not fetch current price (will retry on next check)"
    
    max_price_msg = f" (alert when ≤ ${max_price:.2f})" if max_price else ""
    
    await ctx.send(
        f"✅ Now tracking **{origin.upper()} → {destination.upper()}** on **{departure_date}**{max_price_msg}\n"
        f"{price_msg}\n"
        f"Alert ID: `{alert_id}` | Checking every {CHECK_INTERVAL_MINUTES} minutes"
    )

@bot.command(name="list")
async def list_alerts(ctx):
    """List all your active flight alerts."""
    alerts = get_user_alerts(ctx.author.id)
    
    if not alerts:
        await ctx.send("You have no active flight alerts. Use `!track` to add one!")
        return
    
    embed = discord.Embed(title="✈️ Your Flight Alerts", color=0x00aaff)
    
    for alert in alerts:
        alert_id, user_id, channel_id, origin, dest, date, max_price, last_price, created = alert
        price_info = f"Last price: ${last_price:.2f}" if last_price else "No price data yet"
        max_info = f" | Alert ≤ ${max_price:.2f}" if max_price else ""
        
        embed.add_field(
            name=f"[{alert_id}] {origin} → {dest} on {date}",
            value=f"{price_info}{max_info}",
            inline=False
        )
    
    await ctx.send(embed=embed)

@bot.command(name="remove")
async def remove_alert_cmd(ctx, alert_id: int):
    """
    Remove a flight alert.
    Usage: !remove <alert_id>
    """
    if remove_alert(alert_id, ctx.author.id):
        await ctx.send(f"✅ Alert `{alert_id}` has been removed.")
    else:
        await ctx.send(f"❌ Could not find alert `{alert_id}` or you don't own it.")

@bot.command(name="check")
async def check_now(ctx):
    """Manually trigger a price check for all your alerts."""
    alerts = get_user_alerts(ctx.author.id)
    
    if not alerts:
        await ctx.send("You have no active alerts to check.")
        return
    
    await ctx.send("🔍 Checking prices... (this uses API calls)")
    
    for alert in alerts:
        alert_id, user_id, channel_id, origin, dest, date, max_price, last_price, created = alert
        current_price = get_flight_price(origin, dest, date)
        
        if current_price:
            update_last_price(alert_id, current_price)
            change = ""
            if last_price:
                diff = current_price - last_price
                if diff < 0:
                    change = f" (📉 ${abs(diff):.2f} lower!)"
                elif diff > 0:
                    change = f" (📈 ${diff:.2f} higher)"
            
            await ctx.send(f"**{origin} → {dest}** ({date}): **${current_price:.2f}**{change}")
        else:
            await ctx.send(f"**{origin} → {dest}** ({date}): Could not fetch price")

@bot.command(name="usage")
async def check_usage(ctx):
    """Check how many API calls you might be using."""
    alerts = get_all_alerts()
    checks_per_day = (24 * 60) / CHECK_INTERVAL_MINUTES
    daily_usage = len(alerts) * checks_per_day
    monthly_usage = daily_usage * 30
    
    await ctx.send(
        f"📊 **API Usage Estimate**\n"
        f"Active alerts: {len(alerts)}\n"
        f"Check interval: every {CHECK_INTERVAL_MINUTES} minutes\n"
        f"Est. daily API calls: ~{daily_usage:.0f}\n"
        f"Est. monthly API calls: ~{monthly_usage:.0f}/250"
    )

@tasks.loop(minutes=CHECK_INTERVAL_MINUTES)
async def check_prices():
    """Background task to check all flight prices periodically."""
    print(f"=== SCHEDULED PRICE CHECK ===", flush=True)
    alerts = get_all_alerts()
    
    for alert in alerts:
        alert_id, user_id, channel_id, origin, dest, date, max_price, last_price, created = alert
        
        # Skip past dates
        try:
            if datetime.strptime(date, "%Y-%m-%d").date() < datetime.now().date():
                continue
        except:
            continue
        
        current_price = get_flight_price(origin, dest, date)
        
        if current_price is None:
            continue
        
        should_notify = False
        notification_reason = ""
        
        # Check if price dropped below max_price threshold
        if max_price and current_price <= max_price:
            should_notify = True
            notification_reason = f"🎯 Price is at or below your target of ${max_price:.2f}!"
        
        # Check if price dropped significantly from last check (>5%)
        elif last_price and current_price < last_price * 0.95:
            should_notify = True
            drop = last_price - current_price
            notification_reason = f"📉 Price dropped by ${drop:.2f}!"
        
        # Update stored price
        update_last_price(alert_id, current_price)
        
        if should_notify:
            try:
                channel = bot.get_channel(channel_id)
                if channel:
                    await channel.send(
                        f"<@{user_id}> ✈️ **Flight Alert!**\n"
                        f"**{origin} → {dest}** on **{date}**\n"
                        f"Current price: **${current_price:.2f}**\n"
                        f"{notification_reason}"
                    )
            except Exception as e:
                print(f"Error sending notification: {e}", flush=True)

@check_prices.before_loop
async def before_check_prices():
    await bot.wait_until_ready()

@bot.command(name="flighthelp")
async def flight_help(ctx):
    """Show help for flight alert commands."""
    embed = discord.Embed(
        title="✈️ Flight Alert Bot Commands",
        description="Track flight prices and get notified when they drop!",
        color=0x00aaff
    )
    
    embed.add_field(
        name="!track <origin> <destination> <date> [max_price]",
        value="Start tracking a flight.\nExample: `!track JFK LAX 2025-03-15 300`",
        inline=False
    )
    embed.add_field(
        name="!list",
        value="Show all your active flight alerts",
        inline=False
    )
    embed.add_field(
        name="!check",
        value="Manually check prices for all your alerts",
        inline=False
    )
    embed.add_field(
        name="!remove <alert_id>",
        value="Remove a flight alert",
        inline=False
    )
    embed.add_field(
        name="!usage",
        value="See estimated API usage",
        inline=False
    )
    embed.add_field(
        name="📋 Notes",
        value=f"• Use 3-letter airport codes (JFK, LAX, LHR, etc.)\n"
              f"• Dates must be in YYYY-MM-DD format\n"
              f"• Prices checked every {CHECK_INTERVAL_MINUTES} minutes\n"
              f"• You'll be pinged when prices drop >5% or hit your target\n"
              f"• Free tier: 250 searches/month - use wisely!",
        inline=False
    )
    
    await ctx.send(embed=embed)

if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("Error: DISCORD_TOKEN environment variable not set", flush=True)
        exit(1)
    if not SERPAPI_KEY:
        print("Error: SERPAPI_KEY must be set", flush=True)
        exit(1)
    
    bot.run(DISCORD_TOKEN)
