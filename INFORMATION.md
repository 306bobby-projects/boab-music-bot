* This repository is a fork of the Discord music bot Muse, now renamed to BOAB/Bobby's Old Ass Boombox, located at 306bobby-projects/boab-music-bot
* Updated project documentation (README, package.json) to reflect the new name.
* Updated CI/CD workflow (publish.yml) to push to ghcr.io/306bobby-projects/boab and removed legacy upstream pushes.
* Repository uses `yt-dlp` (via execa wrapper) and discord.js v14. Unused `ytsr` dependency removed.
* Improved music queue stability by adding error handling in `player.ts` to prevent crashes on playback failure.
* Switched from `@distube/ytdl-core` to `yt-dlp` binary for playback consistency.
* Implemented automatic 24-hour update interval for `yt-dlp` binary.
* Docker container now includes `python3` to support `yt-dlp`.
* CI/CD workflows for Lint and Type Check upgraded to use `actions/checkout@v4` and `setup-node@v4` to fix cache errors.
* Added `commit-snapshot.yml` workflow to build Docker snapshots on every push.
* Snapshot builds are now restricted to x86 (`linux/amd64`) only.
* Fixed `pr-release.yml` and `publish.yml` to use correct registry and single-arch artifacts.
