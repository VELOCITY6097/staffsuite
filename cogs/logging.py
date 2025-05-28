import discord
from discord.ext import commands
from utils.mongo import db

class Logging(commands.Cog):
    """Event logging: joins, leaves, deletes, edits."""
    def __init__(self, bot):
        self.bot = bot

    async def log_event(self, guild_id, message):
        rec = db.settings.find_one({'guild_id': guild_id}) or {}
        log_channel_id = rec.get('mod_logs')
        if log_channel_id:
            ch = self.bot.get_channel(log_channel_id)
            if ch:
                await ch.send(message)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        await self.log_event(member.guild.id, f"👤 {member.mention} joined.")

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        await self.log_event(member.guild.id, f"🚪 {member.mention} left.")

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.author.bot: return
        await self.log_event(message.guild.id,
            f"🗑️ Message deleted in {message.channel.mention} by {message.author.mention}: {message.content}")

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if before.author.bot or before.content == after.content: return
        await self.log_event(before.guild.id,
            f"✏️ Message edited by {before.author.mention} in {before.channel.mention}:\n"+
            f"**Before:** {before.content}\n**After:** {after.content}")

async def setup(bot): await bot.add_cog(Logging(bot))