import re
import json
import requests
from bs4 import BeautifulSoup

def parse_spotify_link(url):
    """
    Parses a Spotify link using high-performance embed scraping.
    This method bypasses the official API's "Premium required" restrictions 
    and handles massive playlists without any API keys.
    """
    url = url.strip()
    
    # Extract ID and Type
    id_match = re.search(r'spotify\.com/(track|album|playlist)/([a-zA-Z0-9]+)', url)
    if not id_match:
        return {'type': 'error', 'message': 'Invalid Spotify URL format.'}
    
    item_type = id_match.group(1)
    item_id = id_match.group(2)
    
    # 1. Handle Single Songs/Albums via OEmbed (Fastest)
    if item_type in ['track', 'album']:
        try:
            oembed_url = f"https://open.spotify.com/oembed?url={url}"
            r = requests.get(oembed_url, timeout=5)
            if r.status_code == 200:
                data = r.json()
                title = data.get('title', 'Unknown')
                # If it's a track, we just want that one query
                if item_type == 'track':
                    return {'type': 'song', 'queries': [title], 'title': title}
                # For albums, OEmbed only gives the album name. We'll try scraping for tracks below.
        except: pass

    # 2. Handle Playlists & Albums via Embed Scraping (Most robust)
    try:
        # We target the /embed/ version of the URL which contains full JSON data
        embed_url = f"https://open.spotify.com/embed/{item_type}/{item_id}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        r = requests.get(embed_url, headers=headers, timeout=10)
        
        # Look for the internal JSON blob (__NEXT_DATA__)
        match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', r.text, re.DOTALL)
        if match:
            data = json.loads(match.group(1))
            
            # Navigate the complex Spotify state tree
            try:
                entity = data['props']['pageProps']['state']['data']['entity']
                title = entity.get('title') or entity.get('name') or "Spotify Collection"
                
                track_queries = []
                
                # Check for playlist trackList
                if 'trackList' in entity:
                    for t in entity['trackList']:
                        t_name = t.get('title')
                        t_artist = t.get('subtitle')
                        if t_name:
                            query = f"{t_name} {t_artist}" if t_artist else t_name
                            track_queries.append(query)
                
                # Check for album tracks (different structure)
                elif 'tracks' in entity and 'items' in entity['tracks']:
                    for t in entity['tracks']['items']:
                        t_name = t.get('name')
                        # Artists in albums are often nested
                        artists = t.get('artists', [])
                        t_artist = artists[0].get('name') if artists else None
                        if t_name:
                            query = f"{t_name} {t_artist}" if t_artist else t_name
                            track_queries.append(query)

                if track_queries:
                    return {'type': item_type, 'queries': track_queries, 'title': title}
            except: pass

        # 3. Fallback: Standard Scraping (Limited to first 30 tracks)
        headers = {'User-Agent': 'Mozilla/5.0'} # Simple UA gets SSR page
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # Extract tracks from links
        track_links = soup.find_all('a', href=re.compile(r'/track/'))
        queries = []
        for link in track_links:
            name = link.get_text().strip()
            if not name: continue
            # Find artist in next sibling or parent
            parent = link.find_parent()
            artist = ""
            if parent:
                a_links = parent.find_all('a', href=re.compile(r'/artist/'))
                if a_links:
                    artist = ", ".join([a.get_text().strip() for a in a_links if a.get_text().strip()])
            
            query = f"{name} {artist}".strip()
            if query and query not in queries:
                queries.append(query)
        
        if queries:
            title_tag = soup.find('meta', property='og:title')
            title = title_tag.get('content', 'Spotify Collection') if title_tag else "Spotify Collection"
            return {'type': item_type, 'queries': queries, 'title': title}

    except Exception as e:
        print(f"Spotify Scraping Error: {e}")

    return {'type': 'error', 'message': 'Spotify blocked all attempts to read this playlist. Try a YouTube link instead!'}
