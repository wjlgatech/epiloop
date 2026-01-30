# Google Gemini CLI Auth (Epiloop plugin)

OAuth provider plugin for **Gemini CLI** (Google Code Assist).

## Enable

Bundled plugins are disabled by default. Enable this one:

```bash
epiloop plugins enable google-gemini-cli-auth
```

Restart the Gateway after enabling.

## Authenticate

```bash
epiloop models auth login --provider google-gemini-cli --set-default
```

## Env vars

- `EPILOOP_GEMINI_OAUTH_CLIENT_ID` / `GEMINI_CLI_OAUTH_CLIENT_ID`
- `EPILOOP_GEMINI_OAUTH_CLIENT_SECRET` / `GEMINI_CLI_OAUTH_CLIENT_SECRET`
