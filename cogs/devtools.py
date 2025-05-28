import os
import discord
from discord.ext import commands
from discord import app_commands

class DevTools(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="resync", description="Reload a cog (optional) and sync slash commands.")
    @app_commands.describe(cog="Optional: Cog to reload (e.g., cogs.example)")
    async def resync(self, interaction: discord.Interaction, cog: str = None):
        if interaction.user.id != 812347860128497694:
            return await interaction.response.send_message("Unauthorized", ephemeral=True)

        await interaction.response.defer(ephemeral=True)

        if cog:
            try:
                await self.bot.unload_extension(cog)
                await self.bot.load_extension(cog)
                await interaction.followup.send(f"✅ Reloaded `{cog}`", ephemeral=True)
            except Exception as e:
                return await interaction.followup.send(f"❌ Reload failed:\n```py\n{e}\n```", ephemeral=True)

        try:
            synced = await self.bot.tree.sync(guild=interaction.guild)
            await interaction.followup.send(f"✅ Synced {len(synced)} commands to `{interaction.guild.name}`", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Sync failed:\n```py\n{e}\n```", ephemeral=True)

    @app_commands.command(name="find", description="Find which cog file owns a slash command, or list all commands.")
    @app_commands.describe(command_name="The command name to find (optional). Use 'all' to list all commands.")
    async def find(self, interaction: discord.Interaction, command_name: str = None):
        await interaction.response.defer(ephemeral=True)

        # If no command_name or 'all' - list all commands grouped by cog file
        if not command_name or command_name.lower() == "all":
            cogs_commands = {}

            for cmd in self.bot.tree.get_commands():
                cog_file = "Unknown file"
                if hasattr(cmd, "cog") and cmd.cog:
                    module_path = cmd.cog.__module__  # e.g., cogs.attendance
                    cog_file = module_path.split('.')[-1] + ".py"
                elif getattr(cmd, "cog_name", None):
                    cog_file = cmd.cog_name + " (module unknown)"

                if cog_file not in cogs_commands:
                    cogs_commands[cog_file] = []
                cogs_commands[cog_file].append(cmd.name)

            msg = "**Slash commands grouped by cog file:**\n"
            for cog_file, cmds in cogs_commands.items():
                cmds_list = ", ".join(sorted(cmds))
                msg += f"**{cog_file}** ({len(cmds)} commands):\n`{cmds_list}`\n\n"

            if len(msg) > 1900:
                import io
                file = io.StringIO(msg)
                file.seek(0)
                await interaction.followup.send("Too many commands, sending as file.", file=discord.File(file, "commands_list.txt"), ephemeral=True)
            else:
                await interaction.followup.send(msg, ephemeral=True)

            return

        # Search for specific command by name (case insensitive)
        command_name_lower = command_name.lower()

        for cmd in self.bot.tree.get_commands():
            if cmd.name.lower() == command_name_lower:
                cog_file = "Unknown file"
                if hasattr(cmd, "cog") and cmd.cog:
                    module_path = cmd.cog.__module__
                    cog_file = module_path.split('.')[-1] + ".py"
                elif getattr(cmd, "cog_name", None):
                    cog_file = cmd.cog_name + " (module unknown)"

                await interaction.followup.send(
                    f"🔍 Command `/{command_name_lower}` is defined in file: `{cog_file}`",
                    ephemeral=True,
                )
                return

        await interaction.followup.send(
            f"❌ Command `/{command_name_lower}` not found in the bot's slash commands.",
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(DevTools(bot))

    # 🔧 Register to test guild at load
    test_guild_id = os.getenv("TEST_GUILD_ID")
    if test_guild_id:
        try:
            guild_obj = discord.Object(id=int(test_guild_id))
            bot.tree.copy_global_to(guild=guild_obj)
            await bot.tree.sync(guild=guild_obj)
            print("✅ Slash commands synced to test guild.")
        except Exception as e:
            print(f"❌ Error syncing to test guild: {e}")
