# Changelog

All notable changes to the BOAB Discord Bot project will be documented in this file.

## [1.0.2] - 2026-03-29

### Added
- **Interactive Queue UI**: Full pagination support (10 tracks per page) directly in the Now Playing message.
- **Queue Shuffle Button**: New 🎲 button in the queue view to instantly re-randomize the upcoming tracks.
- **Apple Music Playlist Support**: Advanced JSON scraping to handle public user playlists up to 300 tracks.
- **High-Performance Spotify Scraping**: Switched to embed-based metadata extraction to bypass API "Premium Required" restrictions and 403 errors.

### Fixed
- **SoundCloud Audio Engine**: Implemented a high-reliability `yt-dlp` stdout piping method to bypass FFmpeg's HLS/TLS security restrictions.
- **Autocomplete Stability**: Reduced search timeout to 2.0s and added interaction expiry checks to prevent "Unknown Interaction" crashes.
- **Crossfade Audio Hitch**: Optimized message editing logic to prevent the Python GIL from stalling the audio thread during song transitions.
- **Album Art Extraction**: Improved fallback logic to reliably fetch high-resolution thumbnails for all platforms.

## [1.0.1] - 2026-03-29

### Fixed
- **Empty Channel Disconnect**: Added a 30-second grace period to prevent accidental leaves.
- **Queue Errors**: Fixed `NoneType` iteration crash on hidden/deleted YouTube videos.
- **Audio Quality**: Switched to linear fading to prevent 16-bit integer clipping distortion.

## [1.0.0] - 2026-03-29

### Added
- **Initial Release**: Robust Python implementation using `discord.py` and `yt-dlp`.
- **DJ Crossfade**: Pydub-powered seamless transitions with DJ sweep filters.
- **Dynamic Silence Removal**: Automatic trimming of dead air at start/end of tracks.
- **Dockerization**: Fully containerized setup with `ffmpeg` and `davey` support.
- **Persistence**: Server-specific settings saved to `server_configs.json`.
