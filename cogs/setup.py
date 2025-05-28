import discord
from discord.ext import commands
from discord import app_commands
from utils.mongo import db

class Settings(commands.Cog):
    """Configure bot: creates @Staff role and #attendance channel if not existing."""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='setup', description='Initialize server: create Staff role and Attendance channel')
    async def setup(self, interaction: discord.Interaction):
        guild = interaction.guild

        # Fetch existing config or empty dict
        cfg = db.settings.find_one({'guild_id': guild.id}) or {}

        # Check or create Staff role
        role_name = cfg.get('staff_role', 'Staff')
        role = discord.utils.get(guild.roles, name=role_name)
        if not role:
            role = await guild.create_role(name='Staff', mentionable=True)
            role_name = role.name  # Update name in case of change

        # Check or create attendance channel
        channel_id = cfg.get('attendance_channel')
        channel = self.bot.get_channel(channel_id) if channel_id else None

        if not channel:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                role: discord.PermissionOverwrite(read_messages=True)
            }
            channel = await guild.create_text_channel('attendance-logs', overwrites=overwrites)
            channel_id = channel.id

        # Save/update settings in DB
        db.settings.update_one(
            {'guild_id': guild.id},
            {'$set': {'staff_role': role_name, 'attendance_channel': channel_id}},
            upsert=True
        )

        await interaction.response.send_message(
            f"✅ Setup complete.\nRole: {role.mention}\nChannel: {channel.mention}",
            ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(Settings(bot))
