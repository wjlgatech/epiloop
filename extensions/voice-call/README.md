# @epiloop/voice-call

Official Voice Call plugin for **Epiloop**.

Providers:
- **Twilio** (Programmable Voice + Media Streams)
- **Telnyx** (Call Control v2)
- **Plivo** (Voice API + XML transfer + GetInput speech)
- **Mock** (dev/no network)

Docs: `https://docs.clawd.bot/plugins/voice-call`
Plugin system: `https://docs.clawd.bot/plugin`

## Install (local dev)

### Option A: install via Epiloop (recommended)

```bash
epiloop plugins install @epiloop/voice-call
```

Restart the Gateway afterwards.

### Option B: copy into your global extensions folder (dev)

```bash
mkdir -p ~/.epiloop/extensions
cp -R extensions/voice-call ~/.epiloop/extensions/voice-call
cd ~/.epiloop/extensions/voice-call && pnpm install
```

## Config

Put under `plugins.entries.voice-call.config`:

```json5
{
  provider: "twilio", // or "telnyx" | "plivo" | "mock"
  fromNumber: "+15550001234",
  toNumber: "+15550005678",

  twilio: {
    accountSid: "ACxxxxxxxx",
    authToken: "your_token"
  },

  plivo: {
    authId: "MAxxxxxxxxxxxxxxxxxxxx",
    authToken: "your_token"
  },

  // Webhook server
  serve: {
    port: 3334,
    path: "/voice/webhook"
  },

  // Public exposure (pick one):
  // publicUrl: "https://example.ngrok.app/voice/webhook",
  // tunnel: { provider: "ngrok" },
  // tailscale: { mode: "funnel", path: "/voice/webhook" }

  outbound: {
    defaultMode: "notify" // or "conversation"
  },

  streaming: {
    enabled: true,
    streamPath: "/voice/stream"
  }
}
```

Notes:
- Twilio/Telnyx/Plivo require a **publicly reachable** webhook URL.
- `mock` is a local dev provider (no network calls).

## CLI

```bash
epiloop voicecall call --to "+15555550123" --message "Hello from Epiloop"
epiloop voicecall continue --call-id <id> --message "Any questions?"
epiloop voicecall speak --call-id <id> --message "One moment"
epiloop voicecall end --call-id <id>
epiloop voicecall status --call-id <id>
epiloop voicecall tail
epiloop voicecall expose --mode funnel
```

## Tool

Tool name: `voice_call`

Actions:
- `initiate_call` (message, to?, mode?)
- `continue_call` (callId, message)
- `speak_to_user` (callId, message)
- `end_call` (callId)
- `get_status` (callId)

## Gateway RPC

- `voicecall.initiate` (to?, message, mode?)
- `voicecall.continue` (callId, message)
- `voicecall.speak` (callId, message)
- `voicecall.end` (callId)
- `voicecall.status` (callId)

## Notes

- Uses webhook signature verification for Twilio/Telnyx/Plivo.
- `responseModel` / `responseSystemPrompt` control AI auto-responses.
- Media streaming requires `ws` and OpenAI Realtime API key.
