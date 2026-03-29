# Changelog

All notable changes to the BOAB Discord Bot project will be documented in this file.

## [1.0.0] - 2026-03-29

### Added
- **Initial Release** of the BOAB Discord Bot.
- **Python-based Engine**: Migration from JS to a robust Python implementation using `discord.py` and `yt-dlp`.
- **Multi-Platform Metadata Extraction**: 
  - YouTube (Video & Playlist support).
  - Apple Music (Song, Album, and User Playlist scraping via iTunes API & JSON extraction).
  - Spotify (Track, Album, and Playlist support via high-performance Embed scraping).
- **Advanced Audio Engine**:
  - **Pydub Crossfading**: Seamless DJ-style transitions between tracks.
  - **DJ Sweep Filters**: Low-pass and volume curve filters applied during crossfade.
  - **Dynamic Silence Removal**: Automatic trimming of silence at the start/end of tracks for tighter transitions.
  - **Crossfade on Skip**: Triggering `/skip` now crossfades to the next song instead of an abrupt cut.
- **Interactive UI**:
  - **Now Playing Embeds**: Real-time progress bar, album art extraction, and playback status.
  - **Button Controls**: Interactive Pause/Resume, Skip, Stop, and Crossfade Toggle buttons.
  - **Queue Paginator**: Interactive `📜 Queue` button with paging support (10 tracks per page).
- **Persistence**: 
  - Server-specific settings (crossfade duration, default state) saved to `server_configs.json`.
- **Infrastructure**:
  - **Dockerization**: Fully containerized setup with automated `ffmpeg` and `davey` library installation.
  - **CI/CD**: GitHub Actions for Python syntax testing and automated GHCR image publishing on version tags.
  - **Connectivity**: Robust 10-second reconnection loop for handling network loss.
  - **Cleanup**: Automatic bot disconnection when voice channels are empty.
