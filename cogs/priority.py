import os
import discord
import random
from discord.ext import commands, tasks
from discord import app_commands
from utils.mongo import db
from datetime import datetime, timedelta
from croniter import croniter

OWNER_ID = int(os.getenv('OWNER_ID', '0'))
PRIOTEST_CHANNEL_ID = int(os.getenv('PRIOTEST', '0'))

def is_owner(interaction: discord.Interaction) -> bool:
    return interaction.user.id == OWNER_ID

class Priority(commands.Cog):
    """Manage subscription keys and Pro activation."""
    def __init__(self, bot):
        self.bot = bot
        self.check_keys.start()
        self.schedule_reports = tasks.loop(minutes=1)(self._schedule_reports)
        self.schedule_reports.start()

    def gen_key(self, duration: str, assigned_user_id: int = None) -> dict:
        unit_map = {'s':'seconds','m':'minutes','h':'hours','d':'days','y':'days','l':None}
        unit = duration[-1]
        amt = int(duration[:-1]) if unit != 'l' else None
        now = datetime.now().astimezone()
        expires = None if unit == 'l' else now + timedelta(**{unit_map[unit]: amt})
        key = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=16))
        rec = {
            'key': key,
            'duration': duration,
            'created_at': now,
            'expires_at': expires,
            'used': False,
            'assigned_user_id': assigned_user_id,
            'warned': False,
            'expired_notified': False
        }
        db.keys.insert_one(rec)
        return rec

    @tasks.loop(minutes=1)
    async def check_keys(self):
        now = datetime.now().astimezone()
        prio_ch = self.bot.get_channel(PRIOTEST_CHANNEL_ID)
        async def send_embed(embed):
            if prio_ch:
                await prio_ch.send(embed=embed)

        for rec in db.keys.find({'used': True}):
            guild_id = rec.get('guild_id')
            expires = rec.get('expires_at')
            assigned = rec.get('assigned_user_id')
            if not expires:
                continue

            if not rec.get('warned') and now >= expires - timedelta(hours=1) and now < expires:
                db.keys.update_one({'_id': rec['_id']}, {'$set': {'warned': True}})
                member_mention = f"<@{assigned}>" if assigned else "Staff"
                embed = discord.Embed(
                    title="⚠️ Pro Subscription Ending Soon",
                    description=(
                        f"Subscription for guild ID `{guild_id}` expires at "
                        f"`{expires.strftime('%Y-%m-%d %H:%M:%S %Z')}`\n"
                        f"Assigned to: {member_mention}\n\n"
                        f"Renew by DMing <@{OWNER_ID}>."
                    ),
                    color=discord.Color.orange(),
                    timestamp=now
                )
                embed.set_footer(text=f"Server ID: {guild_id}")
                await send_embed(embed)

            if not rec.get('expired_notified') and now >= expires:
                db.keys.update_one({'_id': rec['_id']}, {'$set': {'expired_notified': True}})
                member_mention = f"<@{assigned}>" if assigned else "Staff"
                embed = discord.Embed(
                    title="⏳ Pro Subscription Expired",
                    description=(
                        f"Subscription for guild ID `{guild_id}` expired at "
                        f"`{expires.strftime('%Y-%m-%d %H:%M:%S %Z')}`\n"
                        f"Assigned to: {member_mention}\n\n"
                        f"Renew by DMing <@{OWNER_ID}>."
                    ),
                    color=discord.Color.dark_gold(),
                    timestamp=now
                )
                embed.set_footer(text=f"Server ID: {guild_id}")
                await send_embed(embed)

    @app_commands.command(name='generate_key', description='Generate a subscription key.')
    @app_commands.check(is_owner)
    @app_commands.describe(duration='Validity (e.g., 7d,12h,1y,5l)', dm_user='Optional: user to DM the key')
    async def generate_key(self, interaction: discord.Interaction, duration: str, dm_user: discord.Member = None):
        rec = self.gen_key(duration, assigned_user_id=dm_user.id if dm_user else None)
        await interaction.response.send_message(f"🔑 Key `{rec['key']}` generated ({duration}).", ephemeral=True)
        if dm_user:
            try:
                exp_text = rec['expires_at'].strftime('%Y-%m-%d %H:%M:%S %Z') if rec['expires_at'] else 'Never'
                await dm_user.send(f"Your key: `{rec['key']}` (expires {exp_text})")
            except discord.Forbidden:
                pass

    @app_commands.command(name='activate_key', description='Activate a subscription key for this server.')
    @app_commands.describe(key='Subscription key')
    async def activate_key(self, interaction: discord.Interaction, key: str):
        rec = db.keys.find_one({'key': key, 'used': False})
        if not rec:
            return await interaction.response.send_message('🚫 Invalid or already used key.', ephemeral=True)

        now = datetime.now().astimezone()
        expires = rec['expires_at']
        db.keys.update_one({'key': key}, {'$set': {
            'used': True,
            'activated_at': now,
            'expires_at': expires,
            'guild_id': interaction.guild.id
        }})

        member_id = rec.get('assigned_user_id')
        member_mention = f"<@{member_id}>" if member_id else "Staff"
        local_exp = expires.strftime('%Y-%m-%d %H:%M:%S %Z') if expires else 'Never'
        embed = discord.Embed(
            title="✅ Pro Activated",
            description=(
                f"{member_mention}, your Pro features are now active!\n"
                f"Expires at: `{local_exp}`\n\n"
                f"To renew, DM <@{OWNER_ID}>."
            ),
            color=discord.Color.green(),
            timestamp=now
        )
        await interaction.response.send_message(embed=embed)

        prio_ch = self.bot.get_channel(PRIOTEST_CHANNEL_ID)
        if prio_ch:
            embed2 = discord.Embed(
                title="🔓 Pro Subscription Activated",
                description=(
                    f"Server: **{interaction.guild.name}** (`{interaction.guild.id}`)\n"
                    f"Key: `{key}`\n"
                    f"Expires: `{local_exp}`\n"
                    f"Assigned to: {member_mention}"
                ),
                color=discord.Color.green(),
                timestamp=now
            )
            embed2.set_footer(text=f"Activated by: {interaction.user.display_name}")
            await prio_ch.send(embed=embed2)

    @app_commands.command(name='deactivate_key', description='Deactivate a key or user subscription.')
    @app_commands.check(is_owner)
    @app_commands.describe(key='Key to deactivate (optional)', dm_user='User to revoke (optional)')
    async def deactivate_key(self, interaction: discord.Interaction, key: str = None, dm_user: discord.Member = None):
        if not key and not dm_user:
            return await interaction.response.send_message("🚫 Provide either a key or a user.", ephemeral=True)

        now = datetime.now().astimezone()
        q = {'guild_id': interaction.guild.id}
        if key:
            q['key'] = key
        if dm_user:
            q['assigned_user_id'] = dm_user.id

        rec = db.keys.find_one({**q, 'used': False})
        if rec:
            db.keys.delete_one({'_id': rec['_id']})
            return await interaction.response.send_message(f"🗑️ Unused key `{rec['key']}` deleted.", ephemeral=True)

        active = list(db.keys.find({**q, 'used': True}))
        if not active:
            return await interaction.response.send_message("🚫 No matching subscription found.", ephemeral=True)
        for r in active:
            db.keys.update_one({'_id': r['_id']}, {'$set': {'expires_at': now}})
        embed = discord.Embed(
            title="🛑 Pro Deactivated",
            description=f"All Pro features have been disabled for this server.\n\nTo reactivate, DM <@{OWNER_ID}>.",
            color=discord.Color.red(),
            timestamp=now
        )
        await interaction.response.send_message(embed=embed)

        prio_ch = self.bot.get_channel(PRIOTEST_CHANNEL_ID)
        if prio_ch:
            embed2 = discord.Embed(
                title="🔒 Pro Subscription Deactivated",
                description=f"Server: **{interaction.guild.name}** (`{interaction.guild.id}`)",
                color=discord.Color.red(),
                timestamp=now
            )
            embed2.set_footer(text=f"Deactivated by: {interaction.user.display_name}")
            await prio_ch.send(embed=embed2)

    def pro_active(self, guild_id: int) -> bool:
        rec = db.keys.find_one({'guild_id': guild_id, 'used': True})
        return bool(rec and (rec['expires_at'] is None or rec['expires_at'] > datetime.now().astimezone()))

    @app_commands.command(name='bulk_notify', description='[Pro] DM all staff a message.')
    async def bulk_notify(self, interaction: discord.Interaction, message: str):
        if not self.pro_active(interaction.guild.id):
            return await interaction.response.send_message('🚫 Pro not active.', ephemeral=True)

        cfg = db.settings.find_one({'guild_id': interaction.guild.id})
        role = discord.utils.get(interaction.guild.roles, name=cfg.get('staff_role', 'Staff'))
        if not role:
            return await interaction.response.send_message("⚠️ Staff role not set.", ephemeral=True)

        for member in interaction.guild.members:
            if role in member.roles:
                try:
                    await member.send(message)
                except:
                    continue
        await interaction.response.send_message('📣 Broadcast sent.', ephemeral=True)

    async def _schedule_reports(self):
        now = datetime.now().astimezone()
        for sched in db.schedules.find({}):
            cron = sched.get('cron')
            guild_id = sched.get('guild_id')
            channel_id = sched.get('channel_id')
            last_run = sched.get('last_run', now - timedelta(minutes=2))
            iter = croniter(cron, last_run)
            next_time = iter.get_next(datetime)
            if now >= next_time:
                db.schedules.update_one({'_id': sched['_id']}, {'$set': {'last_run': now}})
                ch = self.bot.get_channel(channel_id)
                if ch:
                    await ch.send(sched.get('message', 'Scheduled report'))

async def setup(bot):
    await bot.add_cog(Priority(bot))
