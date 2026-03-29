import discord
import yt_dlp
import asyncio
import audioop
import subprocess
from collections import deque
from config import process_pool, ytdl_format_options, ffmpeg_options

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.AudioSource):
    def __init__(self, source, *, data, requester):
        self.source = source
        self.data = data
        self.requester = requester
        self.title = data.get('title')
        self.url = data.get('url')
        self.duration = data.get('duration', 0)
        self.thumbnail = data.get('thumbnail')

    def read(self):
        return self.source.read()

    def cleanup(self):
        self.source.cleanup()

    @classmethod
    async def from_url(cls, url, requester, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        
        ytdl_stream = yt_dlp.YoutubeDL({
            **ytdl_format_options, 
            'extract_flat': False,
            'format': 'bestaudio/best',
            'quiet': True,
            'noplaylist': True,
        })
        
        data = await loop.run_in_executor(process_pool, lambda: ytdl_stream.extract_info(url, download=False))

        if 'entries' in data:
            data = data['entries'][0]

        # Use yt-dlp to stream the data and pipe it into FFmpeg
        # This bypasses all HLS/TLS protocol issues in FFmpeg
        ytdlp_command = [
            'yt-dlp',
            '--no-warnings',
            '-f', 'bestaudio/best',
            '-o', '-',
            url
        ]
        
        print(f'[Audio] Running yt-dlp pipe for: {url}')
        ytdlp_proc = subprocess.Popen(ytdlp_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # We tell FFmpeg to read from stdin (pipe:0)
        source = discord.FFmpegPCMAudio(
            ytdlp_proc.stdout, 
            pipe=True, 
            before_options=None, 
            options=ffmpeg_options['options']
        )
        
        # We wrap the cleanup to ensure both processes are killed
        original_cleanup = source.cleanup
        def combined_cleanup():
            print(f'[Audio] Cleaning up pipe for: {url}')
            try:
                # Log any stderr from yt-dlp on cleanup if it failed
                if ytdlp_proc.poll() is not None and ytdlp_proc.returncode != 0:
                    err = ytdlp_proc.stderr.read().decode()
                    if err: print(f'[Audio] yt-dlp pipe error: {err}')
                
                ytdlp_proc.terminate()
                ytdlp_proc.wait(timeout=1)
            except: pass
            original_cleanup()
        
        source.cleanup = combined_cleanup
        return cls(source, data=data, requester=requester)

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
        
        self.mixed_buffer = deque()
        self.crossfade_processed = False
        self.crossfade_computing = False

    def _cleanup_track(self, track):
        if hasattr(track, 'cleanup'):
            self.player.bot.loop.run_in_executor(process_pool, track.cleanup)

    def start_crossfade_compute(self):
        if not self.player.crossfade_enabled:
            return
            
        cf_frames = min(int(self.player.crossfade_duration * 50), len(self.a_buffer))
        if cf_frames == 0:
            return
            
        a_frames = list(self.a_buffer)[-cf_frames:]
        self.crossfade_computing = True
        self.player.bot.loop.run_in_executor(process_pool, self._compute_crossfade, cf_frames, a_frames)

    def _compute_crossfade(self, cf_frames, a_frames):
        try:
            from pydub import AudioSegment
            
            b_frames = []
            for _ in range(cf_frames):
                if self.track_b:
                    f = self.track_b.read()
                    if f and len(f) == 3840:
                        b_frames.append(f)
                    else:
                        break
                else:
                    break
            
            while len(b_frames) < len(a_frames):
                b_frames.append(b'\x00' * 3840)

            a_raw = b"".join(a_frames)
            b_raw = b"".join(b_frames)

            seg_a = AudioSegment(data=a_raw, sample_width=2, frame_rate=48000, channels=2)
            seg_b = AudioSegment(data=b_raw, sample_width=2, frame_rate=48000, channels=2)

            cf_ms = len(a_frames) * 20
            
            # DJ Filters
            seg_a = seg_a.low_pass_filter(2500).fade_out(cf_ms)
            seg_b = seg_b.fade_in(cf_ms)
            
            mixed = seg_a.overlay(seg_b)
            mixed_raw = mixed.raw_data
            
            mixed_frames = [mixed_raw[i:i+3840] for i in range(0, len(mixed_raw), 3840)]
            self.mixed_buffer = deque(mixed_frames)
            self.crossfade_processed = True
        except Exception as e:
            print(f"Crossfade compute error: {e}")
        finally:
            self.crossfade_computing = False

    def trigger_skip(self):
        if not self.player.crossfade_enabled or self.is_crossfading or self.crossfade_computing:
            self.finished = True
            return

        self.a_exhausted = True
        self._cleanup_track(self.track_a)
        self.track_a = None

        cf_frames = int(self.player.crossfade_duration * 50)
        
        while len(self.a_buffer) > cf_frames:
            self.a_buffer.pop()

        if self.track_b and not self.crossfade_computing and not self.crossfade_processed:
            self.start_crossfade_compute()
        else:
            self.player.bot.loop.call_soon_threadsafe(self.player.prepare_next_track)

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
                    
                    # Trim trailing silence
                    while self.a_buffer and len(self.a_buffer[-1]) == 3840 and audioop.rms(self.a_buffer[-1], 2) < 256:
                        self.a_buffer.pop()
                        
                    self.player.bot.loop.call_soon_threadsafe(self.player.prepare_next_track)
                else:
                    self.a_buffer.append(frame)

        ready_to_switch = self.a_exhausted and len(self.a_buffer) <= cf_frames
        
        # 1. PLAY PYDUB MIX
        if self.player.crossfade_enabled and ready_to_switch:
            self.is_crossfading = True
            
            if self.crossfade_processed and self.mixed_buffer:
                frame = self.mixed_buffer.popleft()
                if self.a_buffer:
                    self.a_buffer.popleft()
                
                if len(frame) < 3840:
                    frame = frame + b'\x00' * (3840 - len(frame))
                elif len(frame) > 3840:
                    frame = frame[:3840]
                    
                if not self.mixed_buffer:
                    self._cleanup_track(self.track_a)
                    self.track_a = self.track_b
                    self.track_b = None
                    self.a_exhausted = False
                    self.is_crossfading = False
                    self.crossfade_processed = False
                    self.player.bot.loop.call_soon_threadsafe(self.player.on_track_transition)
                    
                return audioop.mul(frame, 2, self.player.volume)

        # 2. STANDARD PLAYBACK / FALLBACK
        self.is_crossfading = False
        
        frame_a = b'\x00' * 3840
        has_a = False
        if self.a_buffer:
            frame_a = self.a_buffer.popleft()
            has_a = True

        frame_b = b'\x00' * 3840
        has_b = False
        if self.track_b and ready_to_switch and not self.player.crossfade_enabled:
            frame_b = self.track_b.read()
            if frame_b and len(frame_b) == 3840:
                has_b = True
            else:
                self.track_b = None

        if not has_a and not has_b:
            if self.a_exhausted:
                self.finished = True
            return b''

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

        # 3. EMERGENCY AUDIOOP CROSSFADE
        if self.player.crossfade_enabled and ready_to_switch and has_a:
            if self.track_b:
                f_b = self.track_b.read()
                if f_b and len(f_b) == 3840:
                    frame_b = f_b
                    has_b = True
            
            if has_b:
                self.is_crossfading = True
                progress = len(self.a_buffer) / max(1, cf_frames)
                vol_a = progress
                vol_b = 1.0 - progress
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

        return audioop.mul(frame_a, 2, self.player.volume)

    def cleanup(self):
        self._cleanup_track(self.track_a)
        self._cleanup_track(self.track_b)
