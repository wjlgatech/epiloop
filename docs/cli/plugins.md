---
summary: "CLI reference for `epiloop plugins` (list, install, enable/disable, doctor)"
read_when:
  - You want to install or manage in-process Gateway plugins
  - You want to debug plugin load failures
---

# `epiloop plugins`

Manage Gateway plugins/extensions (loaded in-process).

Related:
- Plugin system: [Plugins](/plugin)
- Plugin manifest + schema: [Plugin manifest](/plugins/manifest)
- Security hardening: [Security](/gateway/security)

## Commands

```bash
epiloop plugins list
epiloop plugins info <id>
epiloop plugins enable <id>
epiloop plugins disable <id>
epiloop plugins doctor
epiloop plugins update <id>
epiloop plugins update --all
```

Bundled plugins ship with Epiloop but start disabled. Use `plugins enable` to
activate them.

All plugins must ship a `epiloop.plugin.json` file with an inline JSON Schema
(`configSchema`, even if empty). Missing/invalid manifests or schemas prevent
the plugin from loading and fail config validation.

### Install

```bash
epiloop plugins install <path-or-spec>
```

Security note: treat plugin installs like running code. Prefer pinned versions.

Supported archives: `.zip`, `.tgz`, `.tar.gz`, `.tar`.

Use `--link` to avoid copying a local directory (adds to `plugins.load.paths`):

```bash
epiloop plugins install -l ./my-plugin
```

### Update

```bash
epiloop plugins update <id>
epiloop plugins update --all
epiloop plugins update <id> --dry-run
```

Updates only apply to plugins installed from npm (tracked in `plugins.installs`).
