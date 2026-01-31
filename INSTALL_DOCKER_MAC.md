# Epiloop Docker Installation for Mac

Complete guide to install epiloop in Docker with WhatsApp and Google Chat channels.

## Prerequisites

1. **Docker Desktop for Mac** - [Download here](https://www.docker.com/products/docker-desktop/)
2. **Anthropic API Key** - [Get one here](https://console.anthropic.com/)
3. **For WhatsApp**: A phone number (preferably a spare number)
4. **For Google Chat**: A Google Cloud project with Chat API enabled

---

## Step 1: Install Docker Desktop

```bash
# Option A: Homebrew (recommended)
brew install --cask docker

# Option B: Download from docker.com and install manually
```

Start Docker Desktop and wait for it to be ready (whale icon in menu bar).

---

## Step 2: Clone and Prepare Epiloop

```bash
# Navigate to your epiloop project
cd ~/Documents/Projects/epiloop

# Create directories for config and workspace
mkdir -p ~/.epiloop
mkdir -p ~/clawd
```

---

## Step 3: Create Environment File

Create `~/.epiloop/.env` with your API keys:

```bash
cat > ~/.epiloop/.env << 'EOF'
# Required: At least one LLM provider
ANTHROPIC_API_KEY=sk-ant-your-key-here

# Optional: Additional providers
# OPENAI_API_KEY=sk-your-openai-key
# GOOGLE_API_KEY=your-google-api-key
# OPENROUTER_API_KEY=sk-or-your-key

# Gateway token (auto-generated if empty)
EPILOOP_GATEWAY_TOKEN=

# Config paths
EPILOOP_CONFIG_DIR=~/.epiloop
EPILOOP_WORKSPACE_DIR=~/clawd
EOF
```

---

## Step 4: Build and Start Epiloop

```bash
cd ~/Documents/Projects/epiloop

# Run the setup script (builds image + runs onboarding)
./docker-setup.sh
```

**During onboarding, select:**
- Gateway bind: `lan`
- Gateway auth: `token`
- Install Gateway daemon: `No` (Docker handles this)

---

## Step 5: Verify Gateway is Running

```bash
# Check container status
docker compose ps

# View logs
docker compose logs -f epiloop-gateway

# Get dashboard URL
docker compose run --rm epiloop-cli dashboard --no-open
```

Open the dashboard URL in your browser (includes auth token).

---

## Step 6: Set Up WhatsApp Channel

### 6.1 Configure WhatsApp

Edit `~/.epiloop/epiloop.json`:

```json
{
  "channels": {
    "whatsapp": {
      "enabled": true,
      "dmPolicy": "allowlist",
      "allowFrom": ["+1YOURNUMBER"]
    }
  }
}
```

Replace `+1YOURNUMBER` with your phone number in E.164 format (e.g., `+15551234567`).

### 6.2 Login via QR Code

```bash
# This will display a QR code in your terminal
docker compose run --rm epiloop-cli channels login
```

1. Open WhatsApp on your phone
2. Go to **Settings → Linked Devices → Link a Device**
3. Scan the QR code displayed in terminal
4. Wait for "Login successful" message

### 6.3 Restart Gateway

```bash
docker compose restart epiloop-gateway
```

### 6.4 Test WhatsApp

Send a message to the phone number you linked (or to yourself if using personal number):
- "Hello" → Should get a response from epiloop

---

## Step 7: Set Up Google Chat Channel

### 7.1 Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable the **Google Chat API**:
   - Navigate to **APIs & Services → Enable APIs**
   - Search for "Google Chat API" and enable it

### 7.2 Create Service Account

1. Go to **APIs & Services → Credentials**
2. Click **Create Credentials → Service Account**
3. Name it (e.g., `epiloop-chat`)
4. Skip permissions (Continue)
5. Skip user access (Done)
6. Click on the service account you created
7. Go to **Keys** tab
8. Click **Add Key → Create new key → JSON**
9. Save the downloaded file to `~/.epiloop/googlechat-service-account.json`

### 7.3 Create Chat App

1. Go to [Chat API Configuration](https://console.cloud.google.com/apis/api/chat.googleapis.com/hangouts-chat)
2. Fill in:
   - **App name**: `Epiloop`
   - **Avatar URL**: `https://clawd.bot/logo.png`
   - **Description**: `Personal AI Assistant`
3. Enable **Interactive features**
4. Check **Join spaces and group conversations**
5. Under **Connection settings**: Select **HTTP endpoint URL**
6. Set the endpoint URL (you'll need a public URL - see 7.5)
7. Under **Visibility**: Check **Make this Chat app available to specific people**
8. Enter your email address
9. Click **Save**
10. **Important**: After saving, change **App status** to **Live - available to users**

### 7.4 Configure Epiloop for Google Chat

Edit `~/.epiloop/epiloop.json`:

```json
{
  "channels": {
    "whatsapp": {
      "enabled": true,
      "dmPolicy": "allowlist",
      "allowFrom": ["+1YOURNUMBER"]
    },
    "googlechat": {
      "enabled": true,
      "serviceAccountFile": "/home/node/.epiloop/googlechat-service-account.json",
      "audienceType": "app-url",
      "audience": "https://YOUR-PUBLIC-URL/googlechat",
      "webhookPath": "/googlechat",
      "dm": {
        "policy": "allowlist",
        "allowFrom": ["your-email@gmail.com"]
      }
    }
  }
}
```

### 7.5 Expose Webhook Publicly

Google Chat requires a public HTTPS endpoint. Options:

**Option A: Tailscale Funnel (Recommended)**
```bash
# Install Tailscale if not already
brew install tailscale

# Expose only the webhook path publicly
tailscale funnel --bg --set-path /googlechat http://127.0.0.1:18789/googlechat

# Get your public URL
tailscale funnel status
# Output: https://your-machine.your-tailnet.ts.net/googlechat
```

**Option B: ngrok (Quick testing)**
```bash
brew install ngrok
ngrok http 18789
# Use the https URL + /googlechat
```

### 7.6 Update Google Chat App with Public URL

1. Go back to [Chat API Configuration](https://console.cloud.google.com/apis/api/chat.googleapis.com/hangouts-chat)
2. Update the **HTTP endpoint URL** to your public URL + `/googlechat`
3. Save changes

### 7.7 Restart Gateway

```bash
docker compose restart epiloop-gateway
```

### 7.8 Test Google Chat

1. Go to [Google Chat](https://chat.google.com/)
2. Click **+** next to Direct Messages
3. Search for your app name (e.g., "Epiloop")
4. Select it and click **Add** or **Chat**
5. Send "Hello" → Should get a response

---

## Common Commands

```bash
# View logs
docker compose logs -f epiloop-gateway

# Check channel status
docker compose run --rm epiloop-cli channels status

# Restart gateway
docker compose restart epiloop-gateway

# Stop everything
docker compose down

# Full reset (deletes data)
docker compose down -v

# Send a test message
docker compose run --rm epiloop-cli agent --message "Hello, what can you do?"
```

---

## Troubleshooting

### WhatsApp: QR code expired
```bash
docker compose run --rm epiloop-cli channels logout
docker compose run --rm epiloop-cli channels login
```

### WhatsApp: Messages not arriving
1. Check `~/.epiloop/epiloop.json` has correct phone number in `allowFrom`
2. Verify gateway is running: `docker compose ps`
3. Check logs: `docker compose logs -f epiloop-gateway | grep -i whatsapp`

### Google Chat: 405 Method Not Allowed
1. Verify `channels.googlechat.enabled: true` in config
2. Restart gateway: `docker compose restart epiloop-gateway`
3. Check channel status: `docker compose run --rm epiloop-cli channels status`

### Google Chat: Auth errors
1. Verify service account file path is correct
2. Check `audienceType` and `audience` match your webhook URL
3. Verify the Chat app status is "Live" in Google Cloud Console

### Container won't start
```bash
# Check for errors
docker compose logs epiloop-gateway

# Rebuild image
docker compose build --no-cache
docker compose up -d
```

---

## Security Notes

1. **WhatsApp**: Use a dedicated number, not your personal one
2. **Google Chat**: Only expose `/googlechat` path publicly, keep dashboard private
3. **API Keys**: Never commit `.env` or `epiloop.json` with API keys to git
4. **Gateway Token**: Keep it secret; regenerate if compromised:
   ```bash
   EPILOOP_GATEWAY_TOKEN=$(openssl rand -hex 32)
   ```

---

## Next Steps

Once both channels are working:

1. **Configure more channels** (Telegram, Discord, Slack):
   ```bash
   docker compose run --rm epiloop-cli channels add --help
   ```

2. **Enable autonomous coding**:
   ```
   /autonomous-coding start "Add user authentication"
   ```

3. **Check documentation**:
   - https://docs.clawd.bot/channels
   - https://docs.clawd.bot/gateway
