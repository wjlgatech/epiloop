---
summary: "CLI reference for `epiloop cron` (schedule and run background jobs)"
read_when:
  - You want scheduled jobs and wakeups
  - You’re debugging cron execution and logs
---

# `epiloop cron`

Manage cron jobs for the Gateway scheduler.

Related:
- Cron jobs: [Cron jobs](/automation/cron-jobs)

Tip: run `epiloop cron --help` for the full command surface.

## Common edits

Update delivery settings without changing the message:

```bash
epiloop cron edit <job-id> --deliver --channel telegram --to "123456789"
```

Disable delivery for an isolated job:

```bash
epiloop cron edit <job-id> --no-deliver
```
