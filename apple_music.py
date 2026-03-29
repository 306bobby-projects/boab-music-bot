import re
import json
import urllib.request
import urllib.error
from bs4 import BeautifulSoup
import requests

def _extract_tracks_from_json(obj, tracks):
    if isinstance(obj, dict):
        if 'artistName' in obj and ('title' in obj or 'name' in obj):
            title = obj.get('title') or obj.get('name')
            artist = obj.get('artistName')
            # Exclude the playlist title itself which often has artistName as the creator
            if title and artist and obj.get('type') != 'playlists':
                tracks.append(f"{title} {artist}")
        for value in obj.values():
            _extract_tracks_from_json(value, tracks)
    elif isinstance(obj, list):
        for item in obj:
            _extract_tracks_from_json(item, tracks)

def parse_apple_music_link(url):
    """
    Parses an Apple Music link and returns a list of search queries (Title + Artist)
    that can be passed to yt-dlp.
    Returns:
        dict: {'type': 'song'|'album'|'playlist'|'error', 'queries': ['Song 1 Artist 1', ...], 'title': 'Name'}
    """
    url = url.strip()
    
    # 1. Handle Albums via iTunes API (Most reliable for metadata)
    album_match = re.search(r'/album/[^/]+/(\d+)(?:\?i=\d+)?$', url)
    if album_match and '?i=' not in url:
        album_id = album_match.group(1)
        try:
            req = urllib.request.Request(f'https://itunes.apple.com/lookup?id={album_id}&entity=song')
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode())
                if data['resultCount'] > 0:
                    queries = []
                    album_name = "Unknown Album"
                    for item in data['results']:
                        if item['wrapperType'] == 'collection':
                            album_name = item['collectionName']
                        elif item['wrapperType'] == 'track':
                            queries.append(f"{item['trackName']} {item['artistName']}")
                    if queries:
                        return {'type': 'album', 'queries': queries, 'title': album_name}
        except: pass

    # 2. Handle Single Songs via iTunes API
    song_id_match = re.search(r'\?i=(\d+)', url) or re.search(r'/song/[^/]+/(\d+)', url)
    if song_id_match:
        song_id = song_id_match.group(1)
        try:
            req = urllib.request.Request(f'https://itunes.apple.com/lookup?id={song_id}')
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode())
                if data['resultCount'] > 0:
                    track = data['results'][0]
                    query = f"{track['trackName']} {track['artistName']}"
                    return {'type': 'song', 'queries': [query], 'title': track['trackName']}
        except: pass

    # 3. Handle User Playlists via Web Scraping (JSON-in-HTML)
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        r = requests.get(url, headers=headers, timeout=10)
        
        # Find the massive JSON blob Apple Music uses for data
        json_matches = re.finditer(r'<script type=\"application/json\".*?>(.*?)</script>', r.text, re.DOTALL)
        
        all_queries = []
        playlist_title = "Apple Music Playlist"
        
        # Look for playlist title in OG tags
        soup = BeautifulSoup(r.text, 'html.parser')
        og_title = soup.find('meta', property='og:title')
        if og_title:
            playlist_title = og_title.get('content', playlist_title).split(' by ')[0].replace('â', '')

        for match in json_matches:
            content = match.group(1).strip()
            if len(content) > 1000: # We only care about the big data blobs
                try:
                    data = json.loads(content)
                    _extract_tracks_from_json(data, all_queries)
                except: continue
        
        if all_queries:
            # Deduplicate while preserving order
            seen = set()
            dedup = [q for q in all_queries if not (q in seen or seen.add(q))]
            return {'type': 'playlist', 'queries': dedup, 'title': playlist_title}
            
    except Exception as e:
        print(f"Scraping Error: {e}")

    # 4. Final Fallback: Simple OG Scraping for Single Songs
    try:
        if not soup:
            r = requests.get(url, headers=headers, timeout=5)
            soup = BeautifulSoup(r.text, 'html.parser')
        title_tag = soup.find('meta', property='og:title')
        if title_tag:
            content = title_tag.get('content', '')
            content = content.replace(' on Apple Music', '').replace(' on Apple\xa0Music', '')
            return {'type': 'song', 'queries': [content], 'title': content.split(' by ')[0]}
    except: pass

    return {'type': 'error', 'message': 'Could not parse Apple Music link.'}
