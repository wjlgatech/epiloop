---
summary: "CLI reference for `epiloop memory` (status/index/search)"
read_when:
  - You want to index or search semantic memory
  - You’re debugging memory availability or indexing
---

# `epiloop memory`

Manage semantic memory indexing and search.
Provided by the active memory plugin (default: `memory-core`; set `plugins.slots.memory = "none"` to disable).

Related:
- Memory concept: [Memory](/concepts/memory)
 - Plugins: [Plugins](/plugins)

## Examples

```bash
epiloop memory status
epiloop memory status --deep
epiloop memory status --deep --index
epiloop memory status --deep --index --verbose
epiloop memory index
epiloop memory index --verbose
epiloop memory search "release checklist"
epiloop memory status --agent main
epiloop memory index --agent main --verbose
```

## Options

Common:

- `--agent <id>`: scope to a single agent (default: all configured agents).
- `--verbose`: emit detailed logs during probes and indexing.

Notes:
- `memory status --deep` probes vector + embedding availability.
- `memory status --deep --index` runs a reindex if the store is dirty.
- `memory index --verbose` prints per-phase details (provider, model, sources, batch activity).
