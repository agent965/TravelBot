import discord
from discord.ext import commands, tasks
import os
import requests
from datetime import datetime, timedelta
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
    """Fetch the cheapest flight details from Google Flights via SerpApi."""
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
            flight = flights[0]
            price = flight.get("price")
            
            if price:
                # Get flight leg details
                legs = flight.get("flights", [])
                airline = "Unknown"
                departure_time = ""
                arrival_time = ""
                duration = ""
                stops = len(legs) - 1 if legs else 0
                
                if legs:
                    first_leg = legs[0]
                    airline = first_leg.get("airline", "Unknown")
                    departure_time = first_leg.get("departure_airport", {}).get("time", "")
                    
                    last_leg = legs[-1]
                    arrival_time = last_leg.get("arrival_airport", {}).get("time", "")
                
                # Get total duration
                duration = flight.get("total_duration", 0)
                hours = duration // 60
                mins = duration % 60
                duration_str = f"{hours}h {mins}m" if duration else ""
                
                # Build Google Flights link (one-way)
                # Format: /flights/origin/destination/date
                booking_link = f"https://www.google.com/travel/flights/search?tfs=CBwQAhojEgoyMDI2LTAxLTIwagcIARIDSkZLcgcIARIDTEFYGgA&tfu=EgYIARABGAA&hl=en&gl=us&curr=USD"
                # Simpler fallback link that usually works
                booking_link = f"https://www.google.com/travel/flights?q=one%20way%20flights%20from%20{origin}%20to%20{destination}%20on%20{departure_date}&curr=USD"
                
                print(f"Found: ${price} on {airline} at {departure_time}", flush=True)
                
                return {
                    "price": float(price),
                    "airline": airline,
                    "departure_time": departure_time,
                    "arrival_time": arrival_time,
                    "duration": duration_str,
                    "stops": stops,
                    "link": booking_link
                }
        
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
    """
    Track a flight route. Supports multiple airports with commas.
    Usage: !track SEA NRT,HND 2026-06-15 800
    """
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
    
    # Parse multiple airports (comma-separated)
    origins = [o.strip().upper() for o in origin.split(",")]
    destinations = [d.strip().upper() for d in destination.split(",")]
    
    # Validate airport codes
    for code in origins + destinations:
        if len(code) != 3:
            await ctx.send(f"❌ Invalid airport code: `{code}`. Use 3-letter codes (e.g., JFK, LAX)")
            return
    
    # Get or create user
    user = get_or_create_user(ctx.author.id, str(ctx.author))
    
    # Store channel for notifications
    discord_channels[user['id']] = ctx.channel.id
    
    # Search all combinations
    all_routes = [(o, d) for o in origins for d in destinations]
    
    if len(all_routes) > 6:
        await ctx.send("❌ Too many combinations! Max 6 routes (e.g., 2 origins × 3 destinations)")
        return
    
    await ctx.send(f"🔍 Searching {len(all_routes)} route(s)...")
    
    results = []
    for orig, dest in all_routes:
        flight_data = get_flight_price(orig, dest, departure_date)
        if flight_data:
            flight_data['origin'] = orig
            flight_data['destination'] = dest
            results.append(flight_data)
    
    if not results:
        # Still create alerts for tracking
        for orig, dest in all_routes:
            add_alert(user['id'], orig, dest, departure_date, max_price)
        await ctx.send(
            f"✅ Now tracking **{len(all_routes)} route(s)** for **{departure_date}**\n"
            f"Could not fetch prices right now (will retry later)"
        )
        return
    
    # Find cheapest
    cheapest = min(results, key=lambda x: x['price'])
    
    # Create alerts for all routes
    for orig, dest in all_routes:
        alert = add_alert(user['id'], orig, dest, departure_date, max_price)
        # Update price if we have it
        matching = [r for r in results if r['origin'] == orig and r['destination'] == dest]
        if matching:
            update_last_price(alert['id'], matching[0]['price'])
    
    stops_text = "Nonstop" if cheapest['stops'] == 0 else f"{cheapest['stops']} stop(s)"
    
    embed = discord.Embed(
        title=f"✅ Tracking {len(all_routes)} Route(s)",
        description=f"🏆 **Cheapest: {cheapest['origin']} → {cheapest['destination']}**",
        color=0x00ff00
    )
    embed.add_field(name="💰 One-Way Price", value=f"**${cheapest['price']:.2f}**", inline=True)
    embed.add_field(name="✈️ Airline", value=cheapest['airline'], inline=True)
    embed.add_field(name="🕐 Departure", value=cheapest['departure_time'] or "N/A", inline=True)
    embed.add_field(name="🕐 Arrival", value=cheapest['arrival_time'] or "N/A", inline=True)
    embed.add_field(name="⏱️ Duration", value=cheapest['duration'] or "N/A", inline=True)
    embed.add_field(name="🛑 Stops", value=stops_text, inline=True)
    
    if max_price:
        embed.add_field(name="🎯 Target Price", value=f"${max_price:.2f}", inline=True)
    
    # Show all routes with prices
    if len(results) > 1:
        sorted_results = sorted(results, key=lambda x: x['price'])
        price_list = "\n".join([f"• {r['origin']}→{r['destination']}: ${r['price']:.2f}" for r in sorted_results])
        embed.add_field(name="📊 All Routes", value=price_list, inline=False)
    
    embed.add_field(name="🔗 Book Now", value=f"[Google Flights]({cheapest['link']})", inline=False)
    embed.set_footer(text=f"Date: {departure_date} | Tracking {len(all_routes)} route(s)")
    
    await ctx.send(embed=embed)

@bot.command(name="search")
async def search_flights(ctx, origin: str, destination: str, start_date: str, end_date: str):
    """
    Search for cheapest flight in a date range. Supports multiple airports.
    Usage: !search SEA NRT,HND 2026-06-20 2026-06-30
    """
    print(f"=== SEARCH COMMAND ===", flush=True)
    
    # Validate dates
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        
        if start.date() < datetime.now().date():
            await ctx.send("❌ Start date must be in the future!")
            return
        if end < start:
            await ctx.send("❌ End date must be after start date!")
            return
        
        days_diff = (end - start).days
            
    except ValueError:
        await ctx.send("❌ Invalid date format. Use YYYY-MM-DD (e.g., 2026-06-20 2026-06-30)")
        return
    
    # Parse multiple airports (comma-separated)
    origins = [o.strip().upper() for o in origin.split(",")]
    destinations = [d.strip().upper() for d in destination.split(",")]
    
    # Validate airport codes
    for code in origins + destinations:
        if len(code) != 3:
            await ctx.send(f"❌ Invalid airport code: `{code}`. Use 3-letter codes (e.g., JFK, LAX)")
            return
    
    all_routes = [(o, d) for o in origins for d in destinations]
    total_api_calls = (days_diff + 1) * len(all_routes)
    
    # Limit total API calls
    if total_api_calls > 30:
        await ctx.send(f"❌ Too many API calls ({total_api_calls})! Reduce date range or airports. Max 30 calls.")
        return
    
    await ctx.send(f"🔍 Searching {len(all_routes)} route(s) × {days_diff + 1} days = **{total_api_calls} searches**...")
    
    # Search all combinations
    all_results = []
    
    for orig, dest in all_routes:
        current = start
        while current <= end:
            date_str = current.strftime("%Y-%m-%d")
            flight_data = get_flight_price(orig, dest, date_str)
            
            if flight_data:
                flight_data['date'] = date_str
                flight_data['origin'] = orig
                flight_data['destination'] = dest
                all_results.append(flight_data)
            
            current = current + timedelta(days=1)
    
    if not all_results:
        await ctx.send(f"❌ No flights found for any route in that date range.")
        return
    
    # Find cheapest overall
    cheapest = min(all_results, key=lambda x: x['price'])
    
    stops_text = "Nonstop" if cheapest['stops'] == 0 else f"{cheapest['stops']} stop(s)"
    
    embed = discord.Embed(
        title=f"🏆 Cheapest: {cheapest['origin']} → {cheapest['destination']}",
        description=f"Best price from {start_date} to {end_date}",
        color=0xffd700
    )
    embed.add_field(name="📅 Best Date", value=f"**{cheapest['date']}**", inline=True)
    embed.add_field(name="💰 One-Way Price", value=f"**${cheapest['price']:.2f}**", inline=True)
    embed.add_field(name="✈️ Airline", value=cheapest['airline'], inline=True)
    embed.add_field(name="🕐 Departure", value=cheapest['departure_time'] or "N/A", inline=True)
    embed.add_field(name="⏱️ Duration", value=cheapest['duration'] or "N/A", inline=True)
    embed.add_field(name="🛑 Stops", value=stops_text, inline=True)
    embed.add_field(name="🔗 Book Now", value=f"[Google Flights]({cheapest['link']})", inline=False)
    
    # Show top 5 cheapest options
    if len(all_results) > 1:
        sorted_results = sorted(all_results, key=lambda x: x['price'])[:5]
        price_list = "\n".join([f"• {r['origin']}→{r['destination']} {r['date']}: ${r['price']:.2f}" for r in sorted_results])
        embed.add_field(name="📊 Top 5 Cheapest", value=price_list, inline=False)
    
    embed.set_footer(text=f"Searched {len(all_results)} flights | Use !track to monitor a specific route")
    
    await ctx.send(embed=embed)

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
        flight_data = get_flight_price(alert['origin'], alert['destination'], date_str)
        
        if flight_data:
            old_price = alert['lastPrice']
            update_last_price(alert['id'], flight_data['price'])
            
            change = ""
            if old_price:
                diff = flight_data['price'] - old_price
                if diff < 0:
                    change = f"📉 ${abs(diff):.2f} lower!"
                elif diff > 0:
                    change = f"📈 ${diff:.2f} higher"
            
            stops_text = "Nonstop" if flight_data['stops'] == 0 else f"{flight_data['stops']} stop(s)"
            
            embed = discord.Embed(
                title=f"✈️ {alert['origin']} → {alert['destination']}",
                color=0x00aaff
            )
            embed.add_field(name="💰 One-Way Price", value=f"**${flight_data['price']:.2f}**", inline=True)
            embed.add_field(name="✈️ Airline", value=flight_data['airline'], inline=True)
            embed.add_field(name="🕐 Departure", value=flight_data['departure_time'] or "N/A", inline=True)
            embed.add_field(name="⏱️ Duration", value=flight_data['duration'] or "N/A", inline=True)
            embed.add_field(name="🛑 Stops", value=stops_text, inline=True)
            if change:
                embed.add_field(name="📊 Change", value=change, inline=True)
            embed.add_field(name="🔗 Book", value=f"[Google Flights]({flight_data['link']})", inline=False)
            embed.set_footer(text=f"Date: {date_str}")
            
            await ctx.send(embed=embed)
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
    
    embed.add_field(name="!track SEA NRT 2026-06-15 [max_price]", value="Track a flight", inline=False)
    embed.add_field(name="!track SEA NRT,HND 2026-06-15", value="Track multiple airports (comma-separated)", inline=False)
    embed.add_field(name="!search SEA NRT,HND 2026-06-01 2026-06-14", value="Find cheapest in date range + airports", inline=False)
    embed.add_field(name="!list", value="Show your alerts", inline=False)
    embed.add_field(name="!check", value="Check prices now", inline=False)
    embed.add_field(name="!remove <id>", value="Remove an alert", inline=False)
    embed.add_field(name="💡 Tips", value="• NRT = Tokyo Narita, HND = Tokyo Haneda\n• Max 30 API calls per search\n• Prices are one-way", inline=False)
    
    await ctx.send(embed=embed)

@tasks.loop(minutes=CHECK_INTERVAL_MINUTES)
async def check_prices():
    """Background price checker."""
    print("=== SCHEDULED PRICE CHECK ===", flush=True)
    
    alerts = get_all_active_alerts()
    
    for alert in alerts:
        date_str = alert['departureDate'].strftime("%Y-%m-%d")
        flight_data = get_flight_price(alert['origin'], alert['destination'], date_str)
        
        if not flight_data:
            continue
        
        price = flight_data['price']
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
                    
                    stops_text = "Nonstop" if flight_data['stops'] == 0 else f"{flight_data['stops']} stop(s)"
                    
                    embed = discord.Embed(
                        title=f"🚨 Flight Alert: {alert['origin']} → {alert['destination']}",
                        description=reason,
                        color=0x00ff00
                    )
                    embed.add_field(name="💰 One-Way Price", value=f"**${price:.2f}**", inline=True)
                    embed.add_field(name="✈️ Airline", value=flight_data['airline'], inline=True)
                    embed.add_field(name="🕐 Departure", value=flight_data['departure_time'] or "N/A", inline=True)
                    embed.add_field(name="⏱️ Duration", value=flight_data['duration'] or "N/A", inline=True)
                    embed.add_field(name="🛑 Stops", value=stops_text, inline=True)
                    embed.add_field(name="📅 Date", value=date_str, inline=True)
                    embed.add_field(name="🔗 Book Now", value=f"[Google Flights]({flight_data['link']})", inline=False)
                    
                    await user.send(embed=embed)
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