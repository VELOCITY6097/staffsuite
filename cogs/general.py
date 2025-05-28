import discord
from discord.ext import commands
from discord import app_commands
from utils.mongo import db
from datetime import datetime

class General(commands.Cog):
    """General user commands."""
    def __init__(self, bot): self.bot = bot

    @app_commands.command(name='profile', description='View your activity profile.')
    async def profile(self, interaction: discord.Interaction):
        logs = db.logs.count_documents({'user_id': interaction.user.id, 'guild_id': interaction.guild.id})
        vclogs = db.voice_logs.count_documents({'user_id': interaction.user.id, 'guild_id': interaction.guild.id})
        embed = discord.Embed(title=f"Profile: {interaction.user.display_name}", color=0x00AAFF)
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.add_field(name='Log Entries', value=str(logs), inline=True)
        embed.add_field(name='Voice Events', value=str(vclogs), inline=True)
        embed.set_footer(text=f"As of {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name='ping', description='Check bot latency.')
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"🏓 Pong: {round(self.bot.latency*1000)}ms", ephemeral=True)

    @app_commands.command(name='uptime', description='Show how long the bot has been running.')
    async def uptime(self, interaction: discord.Interaction):
        delta = datetime.utcnow() - self.bot.launch_time
        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        embed = discord.Embed(
            title="🕒 Bot Uptime",
            description=f"`{hours}h {minutes}m {seconds}s`",
            color=discord.Color.blue()
        )
        embed.set_footer(text="Running since " + self.bot.launch_time.strftime("%Y-%m-%d %H:%M:%S UTC"))
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name='feedback', description='Submit feedback to admins.')
    @app_commands.describe(message='Your feedback message')
    async def feedback(self, interaction: discord.Interaction, message: str):
        db.feedback.insert_one({
            'user_id': interaction.user.id,
            'guild_id': interaction.guild.id,
            'message': message,
            'timestamp': datetime.utcnow()
        })
        settings = db.settings.find_one({'guild_id': interaction.guild.id}) or {}
        chan_id = settings.get('feedback_channel')
        if chan_id:
            chan = self.bot.get_channel(chan_id)
            if chan:
                await chan.send(f"📬 Feedback from {interaction.user.mention}: {message}")
        await interaction.response.send_message("🙏 Thanks for your feedback!", ephemeral=True)

    @app_commands.command(name='rules', description='Show server rules.')
    async def rules(self, interaction: discord.Interaction):
        rec = db.settings.find_one({'guild_id': interaction.guild.id}) or {}
        text = rec.get('rules_text', 'No rules set yet.')
        await interaction.response.send_message(text, ephemeral=True)

async def setup(bot): await bot.add_cog(General(bot))