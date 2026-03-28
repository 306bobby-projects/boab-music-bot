import yt_dlp
import random

opts = {'extract_flat': 'in_playlist', 'quiet': True}
with yt_dlp.YoutubeDL(opts) as ydl:
    info = ydl.extract_info('https://www.youtube.com/playlist?list=PLf-ACEhQbewnR7VhZbm9nfRIYZYk3DF8L', download=False)
    entries = [e for e in info['entries'] if e]
    print(f"Original first song: {entries[0]['title']}")
    random.shuffle(entries)
    print(f"Shuffled first song: {entries[0]['title']}")
