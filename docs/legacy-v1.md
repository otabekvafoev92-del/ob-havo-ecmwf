# Osmon v1 (paused 2026-11-14)

The first version of the bot and the site was taken down on 2026-11-14 to be rebuilt from scratch.

- Code: branch `legacy-v1` (the whole repository as it was).
- Bot: the Cloudflare Worker `osmon-bot` now runs the short "new version soon" answer (telegram/worker.js).
  Its old cron triggers were `0 * * * *`, `10,30,50 * * * *`, `20 * * * *`, `40 * * * *`; now only `5 */6 * * *` (clears the old menu).
- Users: the D1 database `osmon` is kept untouched (users, notification settings).
- Site: GitHub Pages shows `placeholder/` (workflow "Site placeholder"); the workflow "Update forecast" (update.yml) is disabled.
- Still running (data only, no site or bot): sat.yml (satellite videos → branch sat), lfl.yml (weather vs last year → branch lfl), obs.yml (stations + 6 h → branch obs).

To bring v1 back: deploy telegram/worker.js from `legacy-v1`, restore the crons above, enable update.yml and run it.
