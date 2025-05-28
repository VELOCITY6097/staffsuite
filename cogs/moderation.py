import os
import discord
from discord.ext import commands
from discord import app_commands
from utils.mongo import db
from datetime import datetime

OWNER_ID = int(os.getenv('OWNER_ID', '0'))

def is_owner(interaction: discord.Interaction) -> bool:
    return interaction.user.id == OWNER_ID

class Moderation(commands.Cog):
    """Moderation commands (owner-only)."""
    def __init__(self, bot): self.bot = bot

    @app_commands.command(name='warn', description='Warn a user with a reason.')
    @app_commands.check(is_owner)
    @app_commands.describe(member='User to warn', reason='Reason for warning')
    async def warn(self, interaction: discord.Interaction, member: discord.Member, reason: str):
        now = datetime.utcnow()
        db.infractions.insert_one({'guild_id': interaction.guild.id,'user_id': member.id,'moderator': interaction.user.id,'reason': reason,'timestamp': now})
        await member.send(f"⚠️ You have been warned: {reason}")
        await interaction.response.send_message(f"✅ {member.mention} has been warned.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Moderation(bot))