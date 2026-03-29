import os
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')

# Dedicated executor for heavy yt-dlp operations
process_pool = ThreadPoolExecutor(max_workers=5)

ytdl_format_options = {
    'format': 'bestaudio/best',
    'restrictfilenames': True,
    'noplaylist': False,
    'nocheckcertificate': True,
    'ignoreerrors': True,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
    'extract_flat': 'in_playlist',
    'no_check_formats': True,
}

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -allowed_extensions ALL -protocol_whitelist file,http,https,tcp,tls,crypto',
    'options': '-vn -threads 1 -af "silenceremove=start_periods=1:start_duration=0.1:start_threshold=-50dB"',
}
