from keep_alive import keep_alive
import os
import aiohttp
import discord
from discord import Embed
from discord.ext import commands, tasks
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO
from keep_alive import app
import datetime
import pytz
from flask import Flask
from threading import Thread

# Umgebungsvariablen laden
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
CHANNEL_ID = int(os.getenv('CHANNEL_ID'))

# Discord Bot Setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Logging aktivieren
import logging
logging.basicConfig(level=logging.INFO)

# V-Bucks Preise
fixedPrices = {
    "500 V-Bucks": "3 €",
    "800 V-Bucks": "6 €",
    "1000 V-Bucks": "7 €",
    "1200 V-Bucks": "8 €",
    "1500 V-Bucks": "10 €",
    "1800 V-Bucks": "13 €",
    "1900 V-Bucks": "13 €",
    "2000 V-Bucks": "14 €",
    "2100 V-Bucks": "15 €",
    "2200 V-Bucks": "15 €",
    "2500 V-Bucks": "17 €",
    "2800 V-Bucks": "19 €",
    "3000 V-Bucks": "21 €",
    "3200 V-Bucks": "22 €",
    "3400 V-Bucks": "24 €",
    "3600 V-Bucks": "25 €",
}

@bot.event
async def on_command_error(ctx, error):
    await ctx.send(f"❌ Fehler: {error}")
    print(f"[Fehler] {error}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    logging.info(f"Befehl empfangen: {message.content} von {message.author}")
    await bot.process_commands(message)

@bot.command()
async def ping(ctx):
    """Antwortet mit der Latenzzeit des Bots"""
    latency = round(bot.latency * 1000)
    await ctx.send(f"🏓 Pong! Latenz: {latency}ms")

# Shopdaten abrufen
async def fetch_shop_data():
    url = 'https://fnitemshop.com/'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate',  # Gzip und Deflate statt Brotli
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',  # Zusätzlicher Header für die Anfrage
        'Cache-Control': 'max-age=0',  # Verhindert das Caching der Anfrage
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    print(f"Fehler beim Laden der Seite: {response.status}")
                    logging.error(f"Fehler beim Laden der Seite: {response.status}")
                    return []
                
                logging.info(f"Seite erfolgreich geladen: {url}")
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                items = []

                for img in soup.find_all('img', {'src': lambda x: x and x.startswith('https://fnitemshop.com/wp-content/uploads')}):
                    imageUrl = img['src']
                    parent = img.find_parent('div', class_='product')
                    name = parent.find('div', class_='product-title').text.strip() if parent else 'Unbekannt'
                    price = parent.find('div', class_='product-price').text.strip() if parent else 'Unbekannt'
                    items.append({'imageUrl': imageUrl, 'name': name, 'price': price})

                logging.info(f"{len(items)} Items geladen")
                return items
        except Exception as e:
            print(f"Fehler beim Abrufen der Seite: {e}")
            logging.error(f"Fehler beim Abrufen der Seite: {e}")
            return []


# Preisliste erstellen
def create_price_text_file():
    text = "V-Bucks Preise für diese Items:\n\n"
    text += '\n'.join([f"{k}: {v}" for k, v in fixedPrices.items()])
    path = "./shop-preise.txt"
    with open(path, 'w', encoding='utf-8') as file:
        file.write(text)
    return path

# Bildcollage erstellen
async def create_image_collage(items):
    canvas_size = 2048
    grid_size = 8
    image_size = canvas_size // grid_size
    canvas = Image.new('RGB', (canvas_size, canvas_size), (30, 30, 30))
    image_count = 0

    async with aiohttp.ClientSession() as session:
        for item in items:
            if not item['imageUrl'].lower().endswith(('jpg', 'jpeg', 'png', 'webp')):
                continue

            try:
                async with session.get(item['imageUrl']) as resp:
                    if resp.status != 200:
                        continue
                    data = await resp.read()
                    img = Image.open(BytesIO(data)).convert("RGB")
                    img = img.resize((image_size, image_size))
                    x = (image_count % grid_size) * image_size
                    y = (image_count // grid_size) * image_size
                    canvas.paste(img, (x, y))
                    image_count += 1
            except Exception as e:
                print(f"Bildfehler: {item['imageUrl']} – {e}")

    buffer = BytesIO()
    canvas.save(buffer, format='PNG')
    buffer.seek(0)
    return buffer

# Shopnachricht senden
async def send_shop_items(channel, items):
    num_per_batch = 64
    total = len(items)
    start = 0
    price_file = create_price_text_file()

    while start < total:
        end = min(start + num_per_batch, total)
        collage = await create_image_collage(items[start:end])
        files = [discord.File(collage, filename="shop-collage.png")]

        if end >= total:
            files.append(discord.File(price_file, filename="shop-preise.txt"))

        await channel.send(
            content="🛒 Hier ist die aktuelle Shop-Auswahl:",
            files=files
        )

        if end >= total:
            embed = Embed(
                title="Jixx's Market",
                description="Zahlung nur per Paypal oder Krypto-Währung möglich.",
                color=0x0099ff
            )
            embed.add_field(name="Zahlungsmethoden", value="💳 Paypal, 💰 Krypto")
            embed.add_field(name="Mindestbestellwert", value="25 €")
            embed.set_footer(text="Vielen Dank für deinen Einkauf!")
            await channel.send(embed=embed)

        start = end

# Täglicher Task
@tasks.loop(minutes=1)
async def scheduled_shop_post():
    tz = pytz.timezone('Europe/Berlin')
    now = datetime.datetime.now(tz)
    if now.hour == 3 and now.minute >= 1:
        logging.info("[Task] Zeit erreicht, versuche Shop zu posten")
        channel = bot.get_channel(CHANNEL_ID)
        if channel:
            items = await fetch_shop_data()
            if items:
                await send_shop_items(channel, items)
            else:
                logging.warning("Keine Items gefunden")
        else:
            logging.warning("Channel nicht gefunden")

# Shop-Befehl per Hand
@bot.command()
async def shop(ctx):
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        await ctx.send("❌ Channel nicht gefunden.")
        return
    items = await fetch_shop_data()
    if items:
        await send_shop_items(channel, items)
        await ctx.send("✅ Shop wurde gepostet!")
    else:
        await ctx.send("❌ Keine Shopdaten gefunden.")

@bot.event
async def on_ready():
    print(f"✅ Bot gestartet als {bot.user}")
    if not scheduled_shop_post.is_running():
        scheduled_shop_post.start()
    logging.info("Scheduled Task gestartet")

# Flask Setup für Uptime Robot Ping
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Bot läuft – Cold Start möglich bei Inaktivität!"

# Flask-Server in einem separaten Thread starten
def run():
    app.run(host="0.0.0.0", port=8080)

# Bot ausführen
if __name__ == "__main__":
    t1 = Thread(target=run)
    t1.start()
    bot.run(TOKEN)
