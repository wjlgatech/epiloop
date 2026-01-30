---
summary: "CLI reference for `epiloop browser` (profiles, tabs, actions, extension relay, remote serve)"
read_when:
  - You use `epiloop browser` and want examples for common tasks
  - You want to control a remote browser via `browser.controlUrl`
  - You want to use the Chrome extension relay (attach/detach via toolbar button)
---

# `epiloop browser`

Manage Epiloop’s browser control server and run browser actions (tabs, snapshots, screenshots, navigation, clicks, typing).

Related:
- Browser tool + API: [Browser tool](/tools/browser)
- Chrome extension relay: [Chrome extension](/tools/chrome-extension)

## Common flags

- `--url <controlUrl>`: override `browser.controlUrl` for this command invocation.
- `--browser-profile <name>`: choose a browser profile (default comes from config).
- `--json`: machine-readable output (where supported).

## Quick start (local)

```bash
epiloop browser --browser-profile chrome tabs
epiloop browser --browser-profile clawd start
epiloop browser --browser-profile clawd open https://example.com
epiloop browser --browser-profile clawd snapshot
```

## Profiles

Profiles are named browser routing configs. In practice:
- `clawd`: launches/attaches to a dedicated Epiloop-managed Chrome instance (isolated user data dir).
- `chrome`: controls your existing Chrome tab(s) via the Chrome extension relay.

```bash
epiloop browser profiles
epiloop browser create-profile --name work --color "#FF5A36"
epiloop browser delete-profile --name work
```

Use a specific profile:

```bash
epiloop browser --browser-profile work tabs
```

## Tabs

```bash
epiloop browser tabs
epiloop browser open https://docs.clawd.bot
epiloop browser focus <targetId>
epiloop browser close <targetId>
```

## Snapshot / screenshot / actions

Snapshot:

```bash
epiloop browser snapshot
```

Screenshot:

```bash
epiloop browser screenshot
```

Navigate/click/type (ref-based UI automation):

```bash
epiloop browser navigate https://example.com
epiloop browser click <ref>
epiloop browser type <ref> "hello"
```

## Chrome extension relay (attach via toolbar button)

This mode lets the agent control an existing Chrome tab that you attach manually (it does not auto-attach).

Install the unpacked extension to a stable path:

```bash
epiloop browser extension install
epiloop browser extension path
```

Then Chrome → `chrome://extensions` → enable “Developer mode” → “Load unpacked” → select the printed folder.

Full guide: [Chrome extension](/tools/chrome-extension)

## Remote browser control (`epiloop browser serve`)

If the Gateway runs on a different machine than the browser, run a standalone browser control server on the machine that runs Chrome:

```bash
epiloop browser serve --bind 127.0.0.1 --port 18791 --token <token>
```

Then point the Gateway at it using `browser.controlUrl` + `browser.controlToken` (or `EPILOOP_BROWSER_CONTROL_TOKEN`).

Security + TLS best-practices: [Browser tool](/tools/browser), [Tailscale](/gateway/tailscale), [Security](/gateway/security)
