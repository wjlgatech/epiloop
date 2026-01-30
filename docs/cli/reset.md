---
summary: "CLI reference for `epiloop reset` (reset local state/config)"
read_when:
  - You want to wipe local state while keeping the CLI installed
  - You want a dry-run of what would be removed
---

# `epiloop reset`

Reset local config/state (keeps the CLI installed).

```bash
epiloop reset
epiloop reset --dry-run
epiloop reset --scope config+creds+sessions --yes --non-interactive
```

