---
summary: "Uninstall Epiloop completely (CLI, service, state, workspace)"
read_when:
  - You want to remove Epiloop from a machine
  - The gateway service is still running after uninstall
---

# Uninstall

Two paths:
- **Easy path** if `epiloop` is still installed.
- **Manual service removal** if the CLI is gone but the service is still running.

## Easy path (CLI still installed)

Recommended: use the built-in uninstaller:

```bash
epiloop uninstall
```

Non-interactive (automation / npx):

```bash
epiloop uninstall --all --yes --non-interactive
npx -y epiloop uninstall --all --yes --non-interactive
```

Manual steps (same result):

1) Stop the gateway service:

```bash
epiloop gateway stop
```

2) Uninstall the gateway service (launchd/systemd/schtasks):

```bash
epiloop gateway uninstall
```

3) Delete state + config:

```bash
rm -rf "${EPILOOP_STATE_DIR:-$HOME/.epiloop}"
```

If you set `EPILOOP_CONFIG_PATH` to a custom location outside the state dir, delete that file too.

4) Delete your workspace (optional, removes agent files):

```bash
rm -rf ~/clawd
```

5) Remove the CLI install (pick the one you used):

```bash
npm rm -g epiloop
pnpm remove -g epiloop
bun remove -g epiloop
```

6) If you installed the macOS app:

```bash
rm -rf /Applications/Epiloop.app
```

Notes:
- If you used profiles (`--profile` / `EPILOOP_PROFILE`), repeat step 3 for each state dir (defaults are `~/.epiloop-<profile>`).
- In remote mode, the state dir lives on the **gateway host**, so run steps 1-4 there too.

## Manual service removal (CLI not installed)

Use this if the gateway service keeps running but `epiloop` is missing.

### macOS (launchd)

Default label is `com.epiloop.gateway` (or `com.epiloop.<profile>`):

```bash
launchctl bootout gui/$UID/com.epiloop.gateway
rm -f ~/Library/LaunchAgents/com.epiloop.gateway.plist
```

If you used a profile, replace the label and plist name with `com.epiloop.<profile>`.

### Linux (systemd user unit)

Default unit name is `epiloop-gateway.service` (or `epiloop-gateway-<profile>.service`):

```bash
systemctl --user disable --now epiloop-gateway.service
rm -f ~/.config/systemd/user/epiloop-gateway.service
systemctl --user daemon-reload
```

### Windows (Scheduled Task)

Default task name is `Epiloop Gateway` (or `Epiloop Gateway (<profile>)`).
The task script lives under your state dir.

```powershell
schtasks /Delete /F /TN "Epiloop Gateway"
Remove-Item -Force "$env:USERPROFILE\.epiloop\gateway.cmd"
```

If you used a profile, delete the matching task name and `~\.epiloop-<profile>\gateway.cmd`.

## Normal install vs source checkout

### Normal install (install.sh / npm / pnpm / bun)

If you used `https://clawd.bot/install.sh` or `install.ps1`, the CLI was installed with `npm install -g epiloop@latest`.
Remove it with `npm rm -g epiloop` (or `pnpm remove -g` / `bun remove -g` if you installed that way).

### Source checkout (git clone)

If you run from a repo checkout (`git clone` + `epiloop ...` / `bun run epiloop ...`):

1) Uninstall the gateway service **before** deleting the repo (use the easy path above or manual service removal).
2) Delete the repo directory.
3) Remove state + workspace as shown above.
