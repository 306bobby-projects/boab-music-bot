# Agent Task List

**Instructions:**
1. Review the entire list below.
2. Select the single most critical task that unblocks other work.
3. Complete the task and change `[ ]` to `[x]`.
4. If a task is too big, break it down into smaller items and add them to this list.

---

- [x] Audit repository for broken or deprecated imports (e.g. discord.js, ytdl-core)
- [x] Rename project docs and readme to new naming. Ignore changelog, it can stay as is
- [x] Add error handling to music queue to prevent crashes
- [ ] Switch to yt-dlp, and make updating this component dynamic in the docker image, updating in a specific time duration (i.e 24 hours)
- [ ] Add a radio functionality, with the chat command syntax "radio *number*" where the queue is auto-populated based on played song and number of songs given. This may need to be youtube specific
- [ ] Run code formatter/linter
- [ ] Review and update all CI workflows (publish.yml updated, others need check)
