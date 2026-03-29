import discord
from discord import app_commands
import yt_dlp
import asyncio
import random
import time
from config import TOKEN, process_pool
from audio import ytdl
from player import MusicPlayer
from settings_manager import update_server_config

class MusicBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.voice_states = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.players = {}

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print('------')
        activity = discord.Activity(type=discord.ActivityType.listening, name="Absolute BANGERS")
        await self.change_presence(activity=activity)
        
        for guild in self.guilds:
            try:
                self.tree.copy_global_to(guild=guild)
                await self.tree.sync(guild=guild)
                print(f"Synced commands to guild: {guild.name}")
            except Exception as e:
                print(f"Failed to sync to {guild.id}: {e}")
        
        print("Bot is fully ready!")

    async def on_disconnect(self):
        print("Bot has disconnected from Discord. Attempting to reconnect...")

    async def on_voice_state_update(self, member, before, after):
        if member.id == self.user.id:
            return
        if before.channel and any(m.id == self.user.id for m in before.channel.members):
            non_bot_members = [m for m in before.channel.members if not m.bot]
            if not non_bot_members:
                vc = before.channel.guild.voice_client
                if vc:
                    player = self.players.get(before.channel.guild.id)
                    if player:
                        await player.stop_player()
                    else:
                        await vc.disconnect()
                    print(f"Left empty voice channel in {before.channel.guild.name}")

    async def close(self):
        for player in list(self.players.values()):
            try: await player.stop_player()
            except: pass
        await super().close()

bot = MusicBot()

def get_player(interaction: discord.Interaction):
    if interaction.guild_id not in bot.players:
        bot.players[interaction.guild_id] = MusicPlayer(interaction, bot)
    return bot.players[interaction.guild_id]

@bot.tree.command(name="config", description="Configure bot settings for this server")
@app_commands.describe(
    crossfade_duration="Length of crossfade in seconds (1-10)",
    default_crossfade="Enable or disable crossfade by default (True/False)"
)
async def config_cmd(interaction: discord.Interaction, crossfade_duration: int = None, default_crossfade: bool = None):
    player = get_player(interaction)
    
    updated = False
    updates = {}
    
    if crossfade_duration is not None:
        if 1 <= crossfade_duration <= 10:
            player.crossfade_duration = crossfade_duration
            updates["crossfade_duration"] = crossfade_duration
            updated = True
        else:
            return await interaction.response.send_message("Please provide a duration between 1 and 10 seconds.", ephemeral=True)
            
    if default_crossfade is not None:
        player.crossfade_enabled = default_crossfade
        updates["crossfade_enabled"] = default_crossfade
        updated = True

    if updated:
        update_server_config(interaction.guild_id, **updates)
        await interaction.response.send_message(
            f"Settings updated:\n"
            f"- Crossfade: **{'ON' if player.crossfade_enabled else 'OFF'}**\n"
            f"- Duration: **{player.crossfade_duration}s**"
        )
    else:
        embed = discord.Embed(title="Server Configuration", color=discord.Color.blue())
        embed.add_field(name="Crossfade Status", value="ON" if player.crossfade_enabled else "OFF", inline=True)
        embed.add_field(name="Crossfade Duration", value=f"{player.crossfade_duration} seconds", inline=True)
        await interaction.response.send_message(embed=embed)


@bot.tree.command(name="play", description="Plays a song or playlist")
@app_commands.describe(
    shuffle="Shuffle the playlist if one is provided",
    immediate="Put the song or playlist next in queue"
)
async def play(interaction: discord.Interaction, query: str, shuffle: bool = False, immediate: bool = False):
    await interaction.response.defer()
    if not interaction.user.voice:
        return await interaction.followup.send("You are not in a voice channel.")
    if not interaction.guild.voice_client:
        await interaction.user.voice.channel.connect()

    player = get_player(interaction)
    search_query = query if query.startswith('http') else f"ytsearch:{query}"

    try:
        loop = bot.loop or asyncio.get_event_loop()
        info = await loop.run_in_executor(process_pool, lambda: ytdl.extract_info(search_query, download=False))
        if not info: return await interaction.followup.send("No results found.")

        if 'entries' in info:
            entries = [e for e in info['entries'] if e]
            if search_query.startswith('ytsearch:'):
                song = entries[0]
                player.add_to_queue(song, interaction.user, immediate=immediate)
                await interaction.followup.send(f"Added **{song.get('title')}** to queue.")
            else:
                if shuffle: 
                    entries = random.sample(entries, len(entries))
                
                added_count = 0
                await interaction.followup.send(f"Processing playlist **{info.get('title', 'Unknown')}** ({len(entries)} songs)...")
                
                processed_entries = []
                for entry in entries:
                    if entry.get('extractor') == 'soundcloud' and entry.get('duration') == 30.0:
                        fallback_query = f"ytsearch1:{entry.get('title')} {entry.get('uploader', '')}"
                        fallback_info = await loop.run_in_executor(process_pool, lambda: ytdl.extract_info(fallback_query, download=False))
                        if fallback_info and 'entries' in fallback_info and fallback_info['entries']:
                            entry = fallback_info['entries'][0]
                    
                    processed_entries.append(entry)
                    added_count += 1
                
                if immediate:
                    for entry in reversed(processed_entries): player.add_to_queue(entry, interaction.user, immediate=True)
                else:
                    for entry in processed_entries: player.add_to_queue(entry, interaction.user, immediate=False)
                    
                await interaction.edit_original_response(content=f"Added **{added_count}** songs to queue from **{info.get('title', 'Unknown')}**.")
        else:
            if info.get('extractor') == 'soundcloud' and info.get('duration') == 30.0:
                fallback_query = f"ytsearch1:{info.get('title')} {info.get('uploader', '')}"
                fallback_info = await loop.run_in_executor(process_pool, lambda: ytdl.extract_info(fallback_query, download=False))
                if fallback_info and 'entries' in fallback_info and fallback_info['entries']:
                    info = fallback_info['entries'][0]

            player.add_to_queue(info, interaction.user, immediate=immediate)
            await interaction.followup.send(f"Added **{info.get('title')}** to queue.")
    except Exception as e:
        await interaction.followup.send(f"Error: {e}")

@play.autocomplete('query')
async def play_autocomplete(interaction: discord.Interaction, current: str):
    if not current or len(current) < 3: return []
    try:
        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(process_pool, lambda: ytdl.extract_info(f"ytsearch5:{current}", download=False))
        return [app_commands.Choice(name=f"{e.get('title', 'Unknown')[:97]}...", value=e.get('webpage_url') or e.get('url')) for e in info['entries'] if e]
    except: return []

@bot.tree.command(name="skip", description="Skips current song")
async def skip(interaction: discord.Interaction):
    if interaction.guild.voice_client and (interaction.guild.voice_client.is_playing() or interaction.guild.voice_client.is_paused()):
        player = bot.players.get(interaction.guild_id)
        if player and player.mixer and player.crossfade_enabled:
            player.mixer.trigger_skip()
        else:
            if player and player.mixer:
                player.mixer.finished = True
            interaction.guild.voice_client.stop()
        await interaction.response.send_message("Skipped!", ephemeral=True)
    else:
        await interaction.response.send_message("Nothing playing.", ephemeral=True)

@bot.tree.command(name="stop", description="Stops music and leaves")
async def stop(interaction: discord.Interaction):
    player = bot.players.get(interaction.guild_id)
    if player: await player.stop_player()
    elif interaction.guild.voice_client: await interaction.guild.voice_client.disconnect()
    await interaction.response.send_message("Stopped.")

@bot.tree.command(name="queue", description="Shows the music queue")
async def queue_cmd(interaction: discord.Interaction):
    player = bot.players.get(interaction.guild_id)
    if not player: return await interaction.response.send_message("Nothing playing.", ephemeral=True)
    embed = discord.Embed(title=f"Queue", color=discord.Color.blue())
    if player.current_song_data: 
        embed.add_field(name="Now Playing", value=player.current_song_data['song'].get('title'), inline=False)
    if player.queue:
        q_list = "\n".join([f"**{i+1}.** {s['song'].get('title')}" for i, s in enumerate(list(player.queue)[:10])])
        embed.add_field(name="Up Next", value=q_list + (f"\n*...and {len(player.queue)-10} more*" if len(player.queue)>10 else ""), inline=False)
    await interaction.response.send_message(embed=embed)

if __name__ == "__main__":
    while True:
        try:
            bot.run(TOKEN)
        except Exception as e:
            print(f"Bot exited with error: {e}")
            print("Retrying connection in 10 seconds...")
            time.sleep(10)
