* This repository is a fork of the Discord music bot Muse, now renamed to BOAB/Bobby's Old Ass Boombox, located at 306bobby-projects/boab-music-bot
* Updated project documentation (README, package.json) to reflect the new name.
* Updated CI/CD workflow (publish.yml) to push to ghcr.io/306bobby-projects/boab and removed legacy upstream pushes.
* Repository uses @distube/ytdl-core and discord.js v14. Unused `ytsr` dependency removed.
* Improved music queue stability by adding error handling in `player.ts` to prevent crashes on playback failure.
