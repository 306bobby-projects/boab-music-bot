import discord
import yt_dlp
import asyncio
import audioop
from collections import deque
from config import process_pool, ytdl_format_options, ffmpeg_options

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, requester, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.requester = requester
        self.title = data.get('title')
        self.url = data.get('url')
        self.duration = data.get('duration', 0)
        self.thumbnail = data.get('thumbnail')

    @classmethod
    async def from_url(cls, url, requester, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        ytdl_stream = yt_dlp.YoutubeDL({**ytdl_format_options, 'extract_flat': False})
        data = await loop.run_in_executor(process_pool, lambda: ytdl_stream.extract_info(url, download=not stream))

        if 'entries' in data:
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl_stream.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data, requester=requester)

class CrossfadeMixer(discord.AudioSource):
    def __init__(self, player):
        self.player = player
        self.track_a = None
        self.track_b = None
        
        self.a_buffer = deque()
        self.a_exhausted = False
        self.finished = False
        self.frames_played = 0
        self.is_crossfading = False

    def _cleanup_track(self, track):
        if hasattr(track, 'cleanup'):
            self.player.bot.loop.run_in_executor(process_pool, track.cleanup)

    def read(self):
        if self.finished:
            return b''

        self.frames_played += 1

        cf_frames = int(self.player.crossfade_duration * 50) if self.player.crossfade_enabled else 0
        lookahead_frames = cf_frames + (30 * 50) 

        if self.track_a and not self.a_exhausted:
            while len(self.a_buffer) < lookahead_frames and not self.a_exhausted:
                frame = self.track_a.read()
                if not frame or len(frame) < 3840:
                    self.a_exhausted = True
                    self.player.bot.loop.call_soon_threadsafe(self.player.prepare_next_track)
                else:
                    self.a_buffer.append(frame)

        frame_a = b'\x00' * 3840
        has_a = False

        if self.a_buffer:
            frame_a = self.a_buffer.popleft()
            has_a = True

        ready_to_switch = self.a_exhausted and len(self.a_buffer) <= cf_frames
        
        frame_b = b'\x00' * 3840
        has_b = False

        if self.track_b and ready_to_switch:
            frame_b = self.track_b.read()
            if frame_b and len(frame_b) == 3840:
                has_b = True
            else:
                self.track_b = None

        if not has_a and not has_b:
            if self.a_exhausted:
                self.finished = True
            return b''

        self.is_crossfading = False

        if self.player.crossfade_enabled and ready_to_switch and has_a and has_b:
            self.is_crossfading = True
            progress = len(self.a_buffer) / max(1, cf_frames)

            vol_a = progress ** 1.5 
            vol_b = (1.0 - progress) ** 1.5

            f_a = audioop.mul(frame_a, 2, vol_a)
            f_b = audioop.mul(frame_b, 2, vol_b)
            mixed = audioop.add(f_a, f_b, 2)

            if len(self.a_buffer) == 0:
                self._cleanup_track(self.track_a)
                self.track_a = self.track_b
                self.track_b = None
                self.a_exhausted = False
                self.is_crossfading = False
                self.player.bot.loop.call_soon_threadsafe(self.player.on_track_transition)
                
            return audioop.mul(mixed, 2, self.player.volume)

        if not self.player.crossfade_enabled and ready_to_switch and len(self.a_buffer) == 0 and has_b:
            self._cleanup_track(self.track_a)
            self.track_a = self.track_b
            self.track_b = None
            self.a_exhausted = False
            self.player.bot.loop.call_soon_threadsafe(self.player.on_track_transition)
            return audioop.mul(frame_b, 2, self.player.volume)

        if has_a and not has_b:
            if self.a_exhausted and len(self.a_buffer) == 0:
                self._cleanup_track(self.track_a)
                self.track_a = None
                self.a_exhausted = False
            return audioop.mul(frame_a, 2, self.player.volume)

        if not has_a and has_b:
            self._cleanup_track(self.track_a)
            self.track_a = self.track_b
            self.track_b = None
            self.a_exhausted = False
            self.player.bot.loop.call_soon_threadsafe(self.player.on_track_transition)
            return audioop.mul(frame_b, 2, self.player.volume)

        return audioop.mul(frame_a, 2, self.player.volume)

    def cleanup(self):
        self._cleanup_track(self.track_a)
        self._cleanup_track(self.track_b)
