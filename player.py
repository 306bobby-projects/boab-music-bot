import discord
import asyncio
from collections import deque
from audio import YTDLSource, CrossfadeMixer
from settings_manager import get_server_config, update_server_config

class MusicControlView(discord.ui.View):
    def __init__(self, player):
        super().__init__(timeout=None)
        self.player = player
        self.update_buttons()

    def update_buttons(self):
        for child in self.children:
            if child.custom_id == "toggle_cf":
                if self.player.crossfade_enabled:
                    child.label = "Crossfade: ON"
                    child.style = discord.ButtonStyle.success
                else:
                    child.label = "Crossfade: OFF"
                    child.style = discord.ButtonStyle.secondary

    @discord.ui.button(label="Pause/Resume", style=discord.ButtonStyle.blurple, emoji="⏯️")
    async def pause_resume(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if not vc:
            return await interaction.response.send_message("Not connected to voice.", ephemeral=True)

        if vc.is_playing():
            vc.pause()
            await interaction.response.send_message("Paused!", ephemeral=True)
        elif vc.is_paused():
            vc.resume()
            await interaction.response.send_message("Resumed!", ephemeral=True)
        else:
            await interaction.response.send_message("Nothing is playing.", ephemeral=True)

    @discord.ui.button(label="Skip", style=discord.ButtonStyle.secondary, emoji="⏭️")
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if not vc or (not vc.is_playing() and not vc.is_paused()):
            return await interaction.response.send_message("Nothing to skip.", ephemeral=True)

        if self.player.mixer and self.player.crossfade_enabled:
            self.player.mixer.trigger_skip()
        else:
            if self.player.mixer:
                self.player.mixer.finished = True
            vc.stop()
        await interaction.response.send_message("Skipped!", ephemeral=True)

    @discord.ui.button(label="Crossfade: OFF", style=discord.ButtonStyle.secondary, emoji="🔀", custom_id="toggle_cf")
    async def toggle_crossfade(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.player.crossfade_enabled = not self.player.crossfade_enabled
        update_server_config(interaction.guild_id, crossfade_enabled=self.player.crossfade_enabled)
        self.update_buttons()
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Stop", style=discord.ButtonStyle.danger, emoji="⏹️")
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.player.stop_player()
        await interaction.response.send_message("Stopped and cleared queue.", ephemeral=True)


class MusicPlayer:
    def __init__(self, interaction: discord.Interaction, bot: discord.Client):
        self.bot = bot
        self.guild = interaction.guild
        self.channel = interaction.channel
        
        self.queue = deque()
        self.queue_event = asyncio.Event()
        
        self.volume = 0.5
        
        config = get_server_config(self.guild.id)
        self.crossfade_enabled = config.get("crossfade_enabled", False)
        self.crossfade_duration = config.get("crossfade_duration", 5)
        
        self.mixer = None
        self.np_message = None
        self.current_song_data = None
        self.next_song_data = None
        
        self.prepare_next_event = asyncio.Event()
        self.np_updater_task = None
        self.bot.loop.create_task(self.player_loop())

    def prepare_next_track(self):
        self.prepare_next_event.set()

    def on_track_transition(self):
        if self.next_song_data:
            self.current_song_data = self.next_song_data
            self.next_song_data = None
            if self.mixer:
                self.mixer.frames_played = 0
            self.bot.loop.create_task(self.resend_np())

    async def get_source(self, song_data, requester):
        try:
            url = song_data.get('webpage_url') or song_data.get('url')
            if not url: return None
            return await YTDLSource.from_url(url, requester, loop=self.bot.loop, stream=True)
        except Exception as e:
            print(f'[Player] Error processing {song_data.get("title", "Unknown")}: {e}')
            return None

    def format_time(self, seconds):
        m, s = divmod(int(seconds), 60)
        h, m = divmod(m, 60)
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"

    def generate_progress_bar(self):
        if not self.mixer or not self.current_song_data:
            return ""
        
        duration = self.current_song_data['song'].get('duration', 0)
        if duration == 0:
            return "🔴 Live"
            
        elapsed = self.mixer.frames_played / 50.0
        elapsed = min(elapsed, duration)
        
        bar_length = 20
        progress = elapsed / duration
        filled = int(bar_length * progress)
        
        bar = "▬" * filled + "🔘" + "▬" * (bar_length - filled - 1)
        if bar_length - filled - 1 < 0:
             bar = "▬" * (bar_length - 1) + "🔘"
            
        return f"`{bar}`\n**{self.format_time(elapsed)} / {self.format_time(duration)}**"

    def build_np_embed(self):
        song_data = self.current_song_data['song']
        requester = self.current_song_data['requester']
        
        url = song_data.get('webpage_url') or song_data.get('url')
        title = song_data.get('title', 'Unknown')
        thumb = song_data.get('thumbnail')
        
        desc = f"[{title}]({url})\n\n{self.generate_progress_bar()}"
        
        if self.mixer and getattr(self.mixer, 'is_crossfading', False):
            desc += "\n\n🔀 **Crossfading to next track...**"
        
        embed = discord.Embed(title="Now Playing", description=desc, color=discord.Color.green())
        if thumb: embed.set_thumbnail(url=thumb)
        embed.add_field(name="Requested By", value=requester.mention)
        return embed

    async def resend_np(self):
        embed = self.build_np_embed()
        view = MusicControlView(self)
        
        if self.np_message:
            try:
                await self.np_message.edit(embed=embed, view=view)
                self.start_np_updater()
                return
            except:
                self.np_message = None

        self.np_message = await self.channel.send(embed=embed, view=view)
        self.start_np_updater()

    def start_np_updater(self):
        if self.np_updater_task and not self.np_updater_task.done():
            self.np_updater_task.cancel()
        self.np_updater_task = self.bot.loop.create_task(self.np_updater_loop())

    async def np_updater_loop(self):
        while not self.bot.is_closed():
            await asyncio.sleep(5)
            if self.np_message and self.mixer and self.current_song_data:
                try:
                    embed = self.build_np_embed()
                    view = MusicControlView(self)
                    await self.np_message.edit(embed=embed, view=view)
                except Exception:
                    pass

    async def player_loop(self):
        await self.bot.wait_until_ready()

        while not self.bot.is_closed():
            if not self.queue:
                try:
                    async with asyncio.timeout(300):
                        self.queue_event.clear()
                        await self.queue_event.wait()
                except asyncio.TimeoutError:
                    return self.destroy()

            queue_item = self.queue.popleft()
            if not self.queue: self.queue_event.clear()

            source = await self.get_source(queue_item['song'], queue_item['requester'])
            if not source: continue

            self.mixer = CrossfadeMixer(self)
            self.mixer.track_a = source
            
            self.current_song_data = queue_item
            await self.resend_np()
            
            self.mixer_finished = asyncio.Event()
            
            if self.guild.voice_client:
                self.guild.voice_client.play(self.mixer, after=lambda _: self.bot.loop.call_soon_threadsafe(self.mixer_finished.set))
            else:
                return self.destroy()

            while not self.mixer.finished:
                self.prepare_next_event.clear()
                
                done, pending = await asyncio.wait(
                    [self.bot.loop.create_task(self.prepare_next_event.wait()),
                     self.bot.loop.create_task(self.mixer_finished.wait())],
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                for task in pending: task.cancel()

                if self.mixer_finished.is_set():
                    break
                    
                if self.prepare_next_event.is_set():
                    next_source = None
                    next_item = None
                    
                    while self.queue and next_source is None:
                        next_item = self.queue.popleft()
                        if not self.queue: self.queue_event.clear()
                        
                        next_source = await self.get_source(next_item['song'], next_item['requester'])
                    
                    if next_source:
                        self.mixer.track_b = next_source
                        self.next_song_data = next_item
                        self.mixer.start_crossfade_compute()
                        
            if self.mixer:
                self.mixer.cleanup()
                self.mixer = None
                
            if self.np_updater_task:
                self.np_updater_task.cancel()

    async def stop_player(self):
        self.queue.clear()
        if self.mixer:
            self.mixer.finished = True
        if self.guild.voice_client:
            await self.guild.voice_client.disconnect()
        self.destroy()

    def add_to_queue(self, item, requester, immediate=False):
        queue_item = {'song': item, 'requester': requester}
        if immediate: self.queue.appendleft(queue_item)
        else: self.queue.append(queue_item)
        self.queue_event.set()

    def destroy(self):
        if self.np_updater_task:
            self.np_updater_task.cancel()
        if self.guild.voice_client:
            self.bot.loop.create_task(self.guild.voice_client.disconnect())
        if self.guild.id in self.bot.players:
            del self.bot.players[self.guild.id]
