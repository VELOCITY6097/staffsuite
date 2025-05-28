import discord
from discord.ext import commands
from discord import app_commands
from utils.mongo import db

class Salary(commands.Cog):
    """Manage staff salaries."""
    def __init__(self, bot): self.bot = bot

    @app_commands.command(name='set_salary', description='Set monthly salary for a staff member.')
    @app_commands.describe(member='Staff member', amount='Salary amount')
    async def set_salary(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        db.salary.update_one({'guild_id': interaction.guild.id, 'user_id': member.id}, {'$set': {'salary': amount}}, upsert=True)
        await interaction.response.send_message(f"💰 {member.mention}'s salary set to ₹{amount}.", ephemeral=True)

    @app_commands.command(name='get_salary', description='Get salary of a staff member.')
    @app_commands.describe(member='Staff member')
    async def get_salary(self, interaction: discord.Interaction, member: discord.Member):
        rec = db.salary.find_one({'guild_id': interaction.guild.id, 'user_id': member.id})
        msg = f"💵 {member.mention} salary is ₹{rec['salary']}" if rec else "No salary set."
        await interaction.response.send_message(msg, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Salary(bot))