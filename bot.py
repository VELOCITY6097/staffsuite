import os
import asyncio
import discord
from datetime import datetime, timezone
from discord.ext import commands
from dotenv import load_dotenv
from utils.mongo import db
from keep_alive import keep_alive

keep_alive()

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
try:
    TEST_GUILD_ID = int(os.getenv("TEST_GUILD_ID", 0))
except Exception:
    TEST_GUILD_ID = 0

try:
    APPLICATION_ID = int(os.getenv("APPLICATION_ID", 0))
except Exception:
    APPLICATION_ID = 0

if not TOKEN:
    print("❌ ERROR: DISCORD_TOKEN not set in .env")
    exit(1)

if APPLICATION_ID == 0:
    print("❌ ERROR: APPLICATION_ID missing or invalid in .env")
    exit(1)

print(f"🔑 Using Application ID: {APPLICATION_ID}")
print(f"🛠️ Test Guild ID: {TEST_GUILD_ID}")

# Set up intents and bot with application_id to avoid sync errors
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents, application_id=APPLICATION_ID)


@bot.event
async def on_ready():
    bot.launch_time = datetime.now(timezone.utc)
    print(f"✅ Bot ready as {bot.user}")
    print("🗃️ Feedback count:", db.feedback.count_documents({}))

    if TEST_GUILD_ID:
        try:
            guild = bot.get_guild(TEST_GUILD_ID)
            if guild is None:
                guild = discord.Object(id=TEST_GUILD_ID)

            synced = await bot.tree.sync(guild=guild)
            print(f"✅ Synced {len(synced)} commands to test guild ({TEST_GUILD_ID})")
        except Exception as e:
            print(f"❌ Sync failed: {e}")
    # If TEST_GUILD_ID not set or zero, skip syncing silently


async def load_cogs():
    cogs_dir = "./cogs"
    for filename in os.listdir(cogs_dir):
        if filename.endswith(".py"):
            cog_name = f"cogs.{filename[:-3]}"
            try:
                await bot.load_extension(cog_name)
                print(f"✅ Loaded {cog_name}")
            except Exception as e:
                print(f"❌ Failed to load {cog_name}: {e}")


async def main():
    async with bot:
        await load_cogs()
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
