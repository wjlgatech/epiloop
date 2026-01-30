---
summary: "CLI reference for `epiloop logs` (tail gateway logs via RPC)"
read_when:
  - You need to tail Gateway logs remotely (without SSH)
  - You want JSON log lines for tooling
---

# `epiloop logs`

Tail Gateway file logs over RPC (works in remote mode).

Related:
- Logging overview: [Logging](/logging)

## Examples

```bash
epiloop logs
epiloop logs --follow
epiloop logs --json
epiloop logs --limit 500
```

