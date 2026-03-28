# Simple Discord Music Bot

A simple Discord music bot that plays YouTube songs and playlists.

## Prerequisites

- Node.js (v16.14.0 or higher)
- Discord Bot Token (already configured in `.env`)
- **IMPORTANT:** In the [Discord Developer Portal](https://discord.com/developers/applications):
    1.  Go to **Bot** settings.
    2.  Enable **Message Content Intent** under the **Privileged Gateway Intents** section.
    3.  Save changes.

## Installation

1.  The project is already set up in this directory.
2.  Install dependencies (if not already done):
    ```bash
    npm install
    ```

## Usage

Start the bot:
```bash
npm start
```

## Commands

- `!play <song name or URL>` - Plays a song or adds it to the queue. Supports YouTube links and playlists.
- `!skip` - Skips the current song.
- `!stop` - Stops the music, clears the queue, and leaves the voice channel.

## Requirements for Voice

- You must be in a voice channel for the `!play` command to work.
- The bot needs permissions to **Connect** and **Speak** in the voice channel.
- The bot needs permissions to **Read Messages** and **Send Messages** in the text channel.
