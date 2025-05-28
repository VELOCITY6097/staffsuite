import discord
from discord.ext import commands
from discord import app_commands
from utils.mongo import db
from datetime import datetime
import asyncio

class Attendance(commands.Cog):
    """Manage sign-in/out and present staff embed with real-time updates."""
    
    def __init__(self, bot):
        self.bot = bot
        self.update_lock = asyncio.Lock()
        self.update_scheduled = {}
        # Cache last embed content hashes to avoid unnecessary edits
        self.last_embed_hash = {}
    
    async def schedule_update(self, guild_id):
        """Debounce multiple updates within 3 seconds for the same guild."""
        async with self.update_lock:
            if self.update_scheduled.get(guild_id):
                return
            self.update_scheduled[guild_id] = True

        await asyncio.sleep(3)  # debounce delay

        await self.update_present_for_guild(guild_id)

        async with self.update_lock:
            self.update_scheduled[guild_id] = False

    async def update_present_for_guild(self, guild_id):
        cfg = db.settings.find_one({'guild_id': guild_id})
        if not cfg:
            print(f"[Attendance] No config found for guild {guild_id}")
            return

        channel_id = cfg.get('attendance_channel')
        message_id = cfg.get('attendance_message_id')  # saved message to edit

        if not channel_id:
            print(f"[Attendance] attendance_channel missing for guild {guild_id}")
            return

        channel = self.bot.get_channel(channel_id)
        if not channel:
            print(f"[Attendance] Cannot find channel ID {channel_id}")
            return

        # Fetch the persistent embed message or send one if missing
        message = None
        if message_id:
            try:
                message = await channel.fetch_message(message_id)
            except discord.NotFound:
                message = None

        # Gather present users (signed in but not signed out)
        now = datetime.utcnow()
        signin_logs = list(db.logs.find({'guild_id': guild_id, 'type': 'signin'}))

        present_users = []
        for log in signin_logs:
            user_id = log['user_id']
            signout = db.logs.find_one({
                'user_id': user_id,
                'guild_id': guild_id,
                'type': 'signout',
                'timestamp': {'$gte': log['timestamp']}
            })
            if signout:
                continue
            present_users.append((user_id, log['timestamp']))

        # Build embed
        embed = discord.Embed(
            title="📋 Staff Attendance - Currently Signed In",
            description=f"Updated at {now.strftime('%Y-%m-%d %H:%M:%S UTC')}",
            color=discord.Color.blue()
        )
        embed.set_footer(text="⏰ Attendance bot | Updates every sign-in/out")
        if self.bot.user.avatar:
            embed.set_thumbnail(url=self.bot.user.avatar.url)

        if not present_users:
            embed.add_field(name="❌ No one is signed in", value="Enjoy your break! 🎉", inline=False)
        else:
            guild = self.bot.get_guild(guild_id)
            for user_id, start_time in present_users:
                member = guild.get_member(user_id) if guild else None
                display_name = member.display_name if member else f"User ID {user_id}"

                duration = now - start_time
                duration_str = str(duration).split('.')[0]  # trim microseconds

                embed.add_field(
                    name=f"👤 {display_name}",
                    value=(
                        f"🕒 **Since:** {start_time.strftime('%H:%M:%S UTC')}\n"
                        f"⏳ **Duration:** {duration_str}"
                    ),
                    inline=False  # full-width field
                )

        # Avoid unnecessary edits
        embed_hash = hash(str(embed.to_dict()))
        if message and self.last_embed_hash.get(guild_id) == embed_hash:
            return
        self.last_embed_hash[guild_id] = embed_hash

        if message:
            try:
                await message.edit(embed=embed)
            except discord.Forbidden:
                print(f"[Attendance] Missing permissions to edit message in channel {channel_id}")
        else:
            try:
                new_message = await channel.send(embed=embed)
                db.settings.update_one({'guild_id': guild_id}, {'$set': {'attendance_message_id': new_message.id}})
            except discord.Forbidden:
                print(f"[Attendance] Missing permissions to send message in channel {channel_id}")

    @app_commands.command(name="signin", description="Sign in to start your duty timer.")
    async def signin(self, interaction: discord.Interaction):
        cfg = db.settings.find_one({'guild_id': interaction.guild.id})
        role_name = cfg.get('staff_role') if cfg else None
        if not role_name:
            return await interaction.response.send_message(
                "⚠️ Configuration missing `staff_role`. Please contact an admin.",
                ephemeral=True
            )

        role = discord.utils.get(interaction.guild.roles, name=role_name)
        if not role or role not in interaction.user.roles:
            return await interaction.response.send_message(
                "🚫 You must have the Staff role to sign in.",
                ephemeral=True
            )

        now = datetime.utcnow()
        db.logs.insert_one({
            'user_id': interaction.user.id,
            'guild_id': interaction.guild.id,
            'type': 'signin',
            'timestamp': now
        })

        await interaction.response.send_message(
            f"✅ {interaction.user.display_name} signed in at {now.strftime('%H:%M:%S UTC')}.",
            ephemeral=True
        )

        await self.schedule_update(interaction.guild.id)

    @app_commands.command(name="signout", description="Sign out and record your work summary.")
    @app_commands.describe(report="Brief summary of your work")
    async def signout(self, interaction: discord.Interaction, report: str):
        now = datetime.utcnow()
        db.logs.insert_one({
            'user_id': interaction.user.id,
            'guild_id': interaction.guild.id,
            'type': 'signout',
            'timestamp': now,
            'report': report
        })

        await interaction.response.send_message(
            f"✅ {interaction.user.display_name} signed out at {now.strftime('%H:%M:%S UTC')}. Report saved.",
            ephemeral=True
        )

        await self.schedule_update(interaction.guild.id)


async def setup(bot):
    await bot.add_cog(Attendance(bot))
