import discord
import asyncio
import random
from collections import deque
from audio import YTDLSource, CrossfadeMixer
from settings_manager import get_server_config, update_server_config

class MusicControlView(discord.ui.View):
    def __init__(self, player):
        super().__init__(timeout=None)
        self.player = player
        self.mode = "np" # "np" or "queue"
        self.queue_page = 0
        self.update_buttons()

    def update_buttons(self):
        self.clear_items()

        if self.mode == "np":
            # PAUSE / RESUME
            btn_pause = discord.ui.Button(label="Pause/Resume", style=discord.ButtonStyle.blurple, emoji="⏯️", custom_id="pause_resume")
            btn_pause.callback = self.pause_resume
            self.add_item(btn_pause)

            # SKIP
            btn_skip = discord.ui.Button(label="Skip", style=discord.ButtonStyle.secondary, emoji="⏭️", custom_id="skip")
            btn_skip.callback = self.skip
            self.add_item(btn_skip)
            
            # QUEUE
            btn_queue = discord.ui.Button(label="Queue", style=discord.ButtonStyle.secondary, emoji="📜", custom_id="show_queue")
            btn_queue.callback = self.show_queue
            self.add_item(btn_queue)

            # CROSSFADE TOGGLE
            cf_label = "Crossfade: ON" if self.player.crossfade_enabled else "Crossfade: OFF"
            cf_style = discord.ButtonStyle.success if self.player.crossfade_enabled else discord.ButtonStyle.secondary
            btn_cf = discord.ui.Button(label=cf_label, style=cf_style, emoji="🔀", custom_id="toggle_cf")
            btn_cf.callback = self.toggle_crossfade
            self.add_item(btn_cf)

            # STOP
            btn_stop = discord.ui.Button(label="Stop", style=discord.ButtonStyle.danger, emoji="⏹️", custom_id="stop")
            btn_stop.callback = self.stop
            self.add_item(btn_stop)

        elif self.mode == "queue":
            # BACK PAGE
            btn_back = discord.ui.Button(label="Back", style=discord.ButtonStyle.secondary, emoji="⬅️", custom_id="queue_back", disabled=(self.queue_page == 0))
            btn_back.callback = self.queue_back
            self.add_item(btn_back)

            # NOW PLAYING
            btn_np = discord.ui.Button(label="Now Playing", style=discord.ButtonStyle.primary, emoji="🎵", custom_id="show_np")
            btn_np.callback = self.show_np
            self.add_item(btn_np)

            # SHUFFLE
            btn_shuffle = discord.ui.Button(label="Shuffle", style=discord.ButtonStyle.secondary, emoji="🎲", custom_id="queue_shuffle")
            btn_shuffle.callback = self.shuffle_queue
            self.add_item(btn_shuffle)

            # NEXT PAGE
            total_pages = max(1, (len(self.player.queue) + 9) // 10)
            btn_next = discord.ui.Button(label="Next", style=discord.ButtonStyle.secondary, emoji="➡️", custom_id="queue_next", disabled=(self.queue_page >= total_pages - 1))
            btn_next.callback = self.queue_next
            self.add_item(btn_next)


    async def pause_resume(self, interaction: discord.Interaction):
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

    async def skip(self, interaction: discord.Interaction):
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

    async def toggle_crossfade(self, interaction: discord.Interaction):
        self.player.crossfade_enabled = not self.player.crossfade_enabled
        update_server_config(interaction.guild_id, crossfade_enabled=self.player.crossfade_enabled)
        self.update_buttons()
        await interaction.response.edit_message(view=self)

    async def stop(self, interaction: discord.Interaction):
        await self.player.stop_player()
        await interaction.response.send_message("Stopped and cleared queue.", ephemeral=True)
        
    async def show_queue(self, interaction: discord.Interaction):
        self.mode = "queue"
        self.queue_page = 0
        self.update_buttons()
        embed = self.player.build_queue_embed(self.queue_page)
        await interaction.response.edit_message(embed=embed, view=self)
        
    async def show_np(self, interaction: discord.Interaction):
        self.mode = "np"
        self.update_buttons()
        embed = self.player.build_np_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    async def shuffle_queue(self, interaction: discord.Interaction):
        if not self.player.queue:
            return await interaction.response.send_message("The queue is empty.", ephemeral=True)
        
        # Convert deque to list, shuffle, then back to deque
        temp_list = list(self.player.queue)
        shuffled = random.sample(temp_list, len(temp_list))
        self.player.queue = deque(shuffled)
        
        self.queue_page = 0
        self.update_buttons()
        embed = self.player.build_queue_embed(self.queue_page)
        await interaction.response.edit_message(embed=embed, view=self)

    async def queue_back(self, interaction: discord.Interaction):
        if self.queue_page > 0:
            self.queue_page -= 1
        self.update_buttons()
        embed = self.player.build_queue_embed(self.queue_page)
        await interaction.response.edit_message(embed=embed, view=self)

    async def queue_next(self, interaction: discord.Interaction):
        total_pages = max(1, (len(self.player.queue) + 9) // 10)
        if self.queue_page < total_pages - 1:
            self.queue_page += 1
        self.update_buttons()
        embed = self.player.build_queue_embed(self.queue_page)
        await interaction.response.edit_message(embed=embed, view=self)


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
            
            # If no URL exists but we have a title (like from an Apple Music album scrape)
            # we do a just-in-time YouTube search to find the audio stream
            if not url and 'title' in song_data:
                from config import process_pool
                from audio import ytdl
                search_query = f"ytsearch1:{song_data['title']}"
                info = await self.bot.loop.run_in_executor(process_pool, lambda: ytdl.extract_info(search_query, download=False))
                if info and 'entries' in info and info['entries']:
                    found_song = info['entries'][0]
                    url = found_song.get('webpage_url') or found_song.get('url')
                    # Update the stored song_data so the embed shows the real thumbnail/title
                    song_data.update(found_song)
            
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

    def build_queue_embed(self, page=0):
        embed = discord.Embed(title=f"Queue for {self.guild.name}", color=discord.Color.blue())
        
        if self.current_song_data: 
            embed.add_field(name="Now Playing", value=self.current_song_data['song'].get('title', 'Unknown'), inline=False)
        else:
            embed.add_field(name="Now Playing", value="Nothing", inline=False)

        if self.queue:
            items_per_page = 10
            total_pages = max(1, (len(self.queue) + items_per_page - 1) // items_per_page)
            
            # Ensure page is within bounds
            page = max(0, min(page, total_pages - 1))
            
            start_idx = page * items_per_page
            end_idx = start_idx + items_per_page
            
            queue_slice = list(self.queue)[start_idx:end_idx]
            
            q_list = "\n".join([f"**{start_idx + i + 1}.** {s['song'].get('title', 'Unknown')}" for i, s in enumerate(queue_slice)])
            
            footer_text = f"Page {page + 1}/{total_pages} | Total Songs: {len(self.queue)}"
            embed.set_footer(text=footer_text)
            
            embed.add_field(name="Up Next", value=q_list, inline=False)
        else:
            embed.add_field(name="Up Next", value="The queue is empty.", inline=False)
            
        return embed

    def build_np_embed(self):
        song_data = self.current_song_data['song']
        requester = self.current_song_data['requester']
        
        url = song_data.get('webpage_url') or song_data.get('url')
        title = song_data.get('title', 'Unknown')
        
        # yt-dlp sometimes puts thumbnails in a list, sometimes directly as 'thumbnail'
        thumb = song_data.get('thumbnail')
        if not thumb and 'thumbnails' in song_data and isinstance(song_data['thumbnails'], list) and len(song_data['thumbnails']) > 0:
            thumb = song_data['thumbnails'][-1].get('url')
        
        # Fallback to standard YouTube thumbnail format if we only have an ID
        if not thumb and song_data.get('id'):
            thumb = f"https://i.ytimg.com/vi/{song_data['id']}/maxresdefault.jpg"
            
        desc = f"[{title}]({url})\n\n{self.generate_progress_bar()}"
        
        if self.mixer and getattr(self.mixer, 'is_crossfading', False):
            desc += "\n\n🔀 **Crossfading to next track...**"
        
        embed = discord.Embed(title="Now Playing", description=desc, color=discord.Color.green())
        if thumb: embed.set_image(url=thumb) # Changed from set_thumbnail to set_image for larger artwork
        embed.add_field(name="Requested By", value=requester.mention)
        return embed

    async def resend_np(self):
        embed = self.build_np_embed()
        self.current_view = MusicControlView(self)
        
        if self.np_message:
            try:
                await self.np_message.edit(embed=embed, view=self.current_view)
                self.start_np_updater()
                return
            except:
                self.np_message = None

        self.np_message = await self.channel.send(embed=embed, view=self.current_view)
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
                    # Only update the embed if we are in "np" mode
                    if hasattr(self, 'current_view') and self.current_view.mode == "np":
                        embed = self.build_np_embed()
                        await self.np_message.edit(embed=embed, view=self.current_view)
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
