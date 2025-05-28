import discord
from discord.ext import commands
from discord import app_commands
from utils.mongo import db
import matplotlib.pyplot as plt
import io
from datetime import datetime

class Reporting(commands.Cog):
    """Generate attendance reports."""
    def __init__(self, bot): self.bot = bot

    @app_commands.command(name='attendance_report', description='Bar chart of sign-ins per user.')
    async def attendance_report(self, interaction: discord.Interaction):
        pipeline = [
            {'$match': {'guild_id': interaction.guild.id, 'type': 'signin'}},
            {'$group': {'_id': '$user_id', 'count': {'$sum': 1}}}
        ]
        data = list(db.logs.aggregate(pipeline))
        if not data:
            return await interaction.response.send_message('No data found.', ephemeral=True)
        names, counts = [], []
        for item in data:
            user = interaction.guild.get_member(item['_id'])
            if user: names.append(user.display_name); counts.append(item['count'])
        plt.figure(figsize=(8,4))
        plt.bar(names, counts)
        plt.xticks(rotation=45, ha='right'); plt.tight_layout()
        buf = io.BytesIO(); plt.savefig(buf, format='png'); buf.seek(0)
        await interaction.response.send_message(file=discord.File(buf, 'attendance.png'))

async def setup(bot):
    await bot.add_cog(Reporting(bot))