# BOAB Discord Bot

A robust, feature-rich Discord music bot built with Python, `discord.py`, and `yt-dlp`. Designed for seamless performance, it supports high-quality streaming from YouTube, SoundCloud, and Spotify, with advanced playback features.

## Features

- **Slash Commands**: Fully integrated with Discord's modern UI (`/play`, `/skip`, `/stop`, `/queue`, `/config`).
- **Platform Support**: Plays songs and playlists from YouTube, SoundCloud, and Spotify. Automatically falls back to YouTube for SoundCloud Premium (GO+) tracks.
- **DJ Crossfade**: Smooth, non-linear crossfading between tracks (simulating a DJ filter sweep) to eliminate awkward silences.
- **Interactive "Now Playing"**: Rich embed messages with playback controls (Pause/Resume, Skip, Stop) and a dynamic progress bar.
- **Advanced Queueing**: 
  - `shuffle`: Randomizes playlists on insertion.
  - `immediate`: Bypasses the queue to play a song or playlist next.
- **Resource Management**: Automatically disconnects when the voice channel is empty to save resources.
- **Dockerized**: Fully containerized for easy deployment and automatic restarts.

## Installation & Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/306bobby-projects/boab-music-bot.git
   cd boab-music-bot
   ```

2. **Configure your environment**:
   Create a `.env` file in the root directory:
   ```env
   DISCORD_TOKEN=your_discord_bot_token_here
   ```

3. **Deploy with Docker** (Recommended):
   The bot includes a complete Docker setup, including `ffmpeg` and Discord's required `davey` encryption library.
   ```bash
   docker compose up -d --build
   ```

## Usage (Commands)

- `/play query:<song/url> [shuffle:True/False] [immediate:True/False]` - Search for a song, or paste a link/playlist. Real-time autocomplete suggestions are available!
- `/skip` - Skip the currently playing track.
- `/stop` - Stop the music, clear the queue, and disconnect the bot.
- `/queue` - View the current "Now Playing" track and the upcoming songs in the queue.
- `/config [crossfade_duration:1-10] [default_crossfade:True/False]` - Adjust server-specific playback settings, such as crossfading behavior.

## Continuous Integration
This project uses GitHub Actions to automatically run syntax checks on commits and publish a new Docker image to the GitHub Container Registry (GHCR) whenever a new version tag (e.g., `v1.0.0`) is pushed.
