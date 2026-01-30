# Visual Progress Dashboard Tutorial

Learn how to use claude-loop's real-time web dashboard to monitor execution progress, track costs, and view logs.

## Table of Contents

- [What is the Dashboard?](#what-is-the-dashboard)
- [Starting the Dashboard](#starting-the-dashboard)
- [Authentication and Tokens](#authentication-and-tokens)
- [Dashboard Overview](#dashboard-overview)
- [Using the Web UI](#using-the-web-ui)
- [Real-time Updates](#real-time-updates)
- [Settings and Customization](#settings-and-customization)
- [Mobile Support](#mobile-support)
- [Troubleshooting](#troubleshooting)

---

## What is the Dashboard?

The Visual Progress Dashboard is a web-based interface that provides real-time visibility into claude-loop executions. Instead of tailing log files or parsing JSON, you get a beautiful, interactive dashboard that updates automatically as work progresses.

### Key Features

- **Live Execution View**: See current story, progress bar, elapsed time, running cost
- **Story Status Grid**: Visual cards showing all stories (complete, in progress, pending)
- **Real-time Logs**: Streaming logs with color-coded messages
- **Cost Tracker**: Token usage, total cost, budget alerts
- **File Changes**: List of modified files with addition/deletion counts
- **Execution History**: Browse past runs with stats
- **Dark Mode**: Easy on the eyes for late-night coding sessions
- **Mobile Responsive**: Check progress from your phone

### How It Works

```
┌─────────────────────────────────────────────┐
│  Dashboard Backend (Flask)                  │
│  - REST API for data                        │
│  - Server-Sent Events for real-time updates │
└────────────┬────────────────────────────────┘
             │
             ├─→ /api/status (execution status)
             ├─→ /api/stories (story list)
             ├─→ /api/logs (log entries)
             ├─→ /api/metrics (cost tracking)
             ├─→ /api/stream (SSE real-time)
             │
┌────────────▼────────────────────────────────┐
│  Dashboard Frontend (Browser)               │
│  - HTML/CSS/JavaScript                      │
│  - Auto-updating UI                         │
│  - localStorage for settings                │
└─────────────────────────────────────────────┘
```

---

## Starting the Dashboard

### Prerequisites

1. **Python 3.8+** with Flask installed:
   ```bash
   pip install flask flask-cors
   ```

2. **claude-loop** working directory

### Basic Start

```bash
./claude-loop.sh dashboard start
```

Output:
```
Starting dashboard server...
Dashboard started on http://localhost:8080 (PID: 12345)
Auth token: AbCdEf123456

Open http://localhost:8080 in your browser
```

The dashboard server runs in the background. Your terminal is free for other work.

### Custom Port

```bash
# Start on port 9000
./claude-loop.sh dashboard start --port 9000

# Access at http://localhost:9000
```

### Custom Host (Remote Access)

```bash
# Allow access from any IP
./claude-loop.sh dashboard start --host 0.0.0.0

# Access from other machines: http://your-ip:8080
```

**Security Note:** When using `0.0.0.0`, ensure you're on a trusted network. The dashboard requires authentication, but use caution with sensitive data.

### Check Dashboard Status

```bash
./claude-loop.sh dashboard status
```

Output:
```
Dashboard is running (PID: 12345)
URL: http://localhost:8080
Uptime: 2h 15m
Auth token: AbCdEf123456
```

### Stopping the Dashboard

```bash
./claude-loop.sh dashboard stop
```

Output:
```
Stopping dashboard (PID: 12345)...
Dashboard stopped successfully
```

---

## Authentication and Tokens

The dashboard uses token-based authentication to prevent unauthorized access.

### Getting Your Token

**Option 1: Check Token File**
```bash
cat .claude-loop/dashboard/auth_token.txt
```

**Option 2: Check Status Output**
```bash
./claude-loop.sh dashboard status
# Shows token in output
```

**Option 3: Generate New Token**
```bash
./claude-loop.sh dashboard generate-token
```

Output:
```
New authentication token generated: XyZ789AbC012
Token saved to .claude-loop/dashboard/auth_token.txt
```

Note: Generating a new token invalidates the old one. Existing browser sessions will need to re-authenticate.

### First-Time Access

1. **Open Dashboard URL**
   ```
   http://localhost:8080
   ```

2. **Enter Authentication Token**
   - On first visit, you'll see a prompt: "Enter authentication token"
   - Copy token from `.claude-loop/dashboard/auth_token.txt`
   - Paste into input field
   - Click "Authenticate"

3. **Token Saved**
   - Token is saved in browser's localStorage
   - You won't be prompted again on this browser
   - Token persists across sessions

### Token Management

**Token Storage:**
- Server: `.claude-loop/dashboard/auth_token.txt`
- Browser: `localStorage.getItem('auth_token')`

**Clearing Token (Log Out):**
```javascript
// In browser console
localStorage.removeItem('auth_token');
location.reload();
```

**Security Best Practices:**
- Don't commit `auth_token.txt` to version control
- Regenerate tokens periodically
- Use HTTPS if exposing dashboard publicly
- Consider VPN for remote access

---

## Dashboard Overview

### Main Sections

```
┌────────────────────────────────────────────────────────────┐
│ 🔄 Claude Loop Dashboard      [Connected]   [🌙]  [⚙️]     │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  Live Execution                          [Pause] [Stop]   │
│  ┌─────────────────────────────────────────────────────┐  │
│  │ Current Story: US-001: User Authentication          │  │
│  │ Progress: [████████░░] 75%                          │  │
│  │ Elapsed: 12m 34s    Running Cost: $1.23            │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                            │
│  Story Status                 ● Complete ● Progress ● Pending│
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐                    │
│  │US-001│ │US-002│ │US-003│ │US-004│                    │
│  │ ✓    │ │ ...  │ │      │ │      │                    │
│  └──────┘ └──────┘ └──────┘ └──────┘                    │
│                                                            │
│  [Logs] [Cost Tracker] [File Changes] [History]          │
│  ┌─────────────────────────────────────────────────────┐  │
│  │ [00:12:34] Starting execution                        │  │
│  │ [00:12:35] Story US-001 complete                     │  │
│  │ [00:12:36] Running tests...                          │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

---

## Using the Web UI

### Story Status Grid

The grid shows all stories from your PRD with color-coded status:

**Complete (Green Border):**
```
┌─ US-001 ───────────┐
│ User Authentication│  ✅
│ Add JWT auth       │
│ Time: 5m  Cost: $0.45│
└────────────────────┘
```

**In Progress (Yellow Border, Pulsing):**
```
┌─ US-002 ───────────┐
│ Password Reset     │  🔄
│ Implement reset... │
│ Running...         │
└────────────────────┘
```

**Pending (Gray Border):**
```
┌─ US-003 ───────────┐
│ Email Verification │
│ Add email verify   │
│ Waiting...         │
└────────────────────┘
```

**Interactions:**
- **Click** on a story card to view details (planned feature)
- **Hover** to see elevation effect
- **Status updates** automatically via SSE

### Logs Tab

Real-time log viewer with automatic scrolling.

**Features:**
- **Color-coded messages**:
  - Info: Gray
  - Success: Green
  - Warning: Yellow
  - Error: Red

- **Auto-scroll toggle**:
  Click "Auto-scroll: ON" to stop automatic scrolling (useful for reading past logs)

- **Clear logs**:
  Click "Clear" button to reset log viewer

- **Timestamps**:
  Each log entry shows `[HH:MM:SS]` timestamp

**Example:**
```
[00:12:34] Starting execution
[00:12:35] ✓ Story US-001 complete
[00:12:36] Running tests...
[00:12:37] ⚠️ Test coverage below 80%
[00:12:38] ❌ Error: Test failed
```

### Cost Tracker Tab

Monitor token usage and costs in real-time.

**Displays:**
- **Total Cost**: Running total in USD
- **Input Tokens**: Tokens sent to API
- **Output Tokens**: Tokens generated
- **Budget Remaining**: Amount left before alert
- **Cost by Story**: Breakdown per user story

**Budget Alert:**
```
⚠️ Budget exceeded! Current: $12.34 / Limit: $10.00
```

When cost exceeds your configured budget limit, you'll see:
- Red alert banner in Cost Tracker
- Browser notification (if enabled)
- Sound alert (if enabled)

**Adjusting Budget:**
Click the settings icon (⚙️) and change "Budget Limit ($)".

### File Changes Tab

See which files were modified during execution.

**Format:**
```
File Changes                    12 files modified

lib/monitoring.sh              +45 -12
claude-loop.sh                 +23 -5
docs/features/new-feature.md   +150 -0
tests/test_monitoring.sh       +67 -3
```

- **Green numbers** (+): Lines added
- **Red numbers** (-): Lines removed
- **Click file** (planned): View full diff

### History Tab

Browse past execution runs.

**Run Entry:**
```
20260113_140523
2026-01-13 14:05:23
Stories: 5/10  Duration: 45m  Cost: $3.21
[View Details]
```

**Features:**
- **Click entry** to load that run's details
- **Refresh button** to update history
- **Sorted** by most recent first

---

## Real-time Updates

### Server-Sent Events (SSE)

The dashboard uses SSE to push updates from server to browser without polling.

**Connection Status:**
- **Connected** (Green dot): Real-time updates working
- **Disconnected** (Red dot): Connection lost, attempting to reconnect
- **Reconnecting** (Yellow dot): Trying to reconnect

**What Updates in Real-Time:**
- Story status changes (pending → in progress → complete)
- Progress bar advancement
- Elapsed time counter
- Running cost
- New log entries
- File changes

**Update Frequency:**
- SSE sends updates immediately when changes occur
- Fallback polling every 2 seconds (configurable)

### Manual Refresh

If real-time updates stop working, you can manually refresh:

1. **Reload page**: `Cmd+R` / `Ctrl+R`
2. **Check connection status**: Top right corner
3. **Check browser console** for errors (F12 → Console)

---

## Settings and Customization

Click the settings icon (⚙️) in the top right to open settings panel.

### Available Settings

**1. Refresh Rate (seconds)**
- **Range**: 1-60 seconds
- **Default**: 2 seconds
- **Purpose**: How often to poll API (in addition to SSE)
- **Lower** = more responsive, more server load
- **Higher** = less responsive, less server load

**2. Budget Limit ($)**
- **Range**: Any positive number
- **Default**: $10.00
- **Purpose**: Alert threshold for execution cost
- **Alert shows** when total cost exceeds this amount

**3. Enable Browser Notifications**
- **Default**: Enabled
- **Requires**: Browser permission (you'll be prompted)
- **Triggers**:
  - Budget exceeded
  - Execution complete
  - Execution failed

**Example notification:**
```
Budget Alert
Cost exceeded $10.00 - Current: $12.34
```

**4. Play Sound on Completion**
- **Default**: Disabled
- **Requires**: Audio file (not included in v1.0)
- **Planned**: Plays notification sound when execution completes

### Saving Settings

Click **"Save Settings"** button after making changes.

Settings are saved to browser's localStorage and persist across:
- Page refreshes
- Browser restarts
- Different tabs (same origin)

### Resetting Settings

```javascript
// In browser console (F12 → Console)
localStorage.clear();
location.reload();
```

This resets all settings to defaults and clears saved auth token.

---

## Dark Mode and Mobile Support

### Dark Mode

Toggle dark mode by clicking the moon icon (🌙) in the top right.

**Features:**
- Smooth color transitions
- Accessible contrast ratios
- Persists across sessions
- Automatically adjusts all UI elements

**Colors:**
- **Light Mode**: White background, dark text
- **Dark Mode**: Dark gray background, light text

**Manual Toggle:**
```javascript
// In browser console
document.body.classList.toggle('dark-mode');
```

### Mobile Support

The dashboard is fully responsive and works on:
- **Desktop** (> 768px): 4-column story grid, side-by-side layouts
- **Tablet** (768px - 480px): 2-column story grid, stacked layouts
- **Mobile** (< 480px): 1-column story grid, full-width elements

**Mobile Optimizations:**
- Touch-friendly buttons
- Scrollable tabs
- Collapsible settings panel
- Readable font sizes

**Testing on Mobile:**
1. Start dashboard with `--host 0.0.0.0`
2. Find your computer's IP: `ifconfig` / `ipconfig`
3. Open `http://your-ip:8080` on your phone
4. Enter auth token

---

## Troubleshooting

### Cannot Connect to Dashboard

**Problem**: Browser shows "Failed to connect to dashboard API"

**Solutions:**

1. **Check dashboard is running:**
   ```bash
   ./claude-loop.sh dashboard status
   ```

2. **Verify URL is correct:**
   - Default: `http://localhost:8080`
   - Custom port: Check port in status output

3. **Check firewall:**
   ```bash
   # On macOS/Linux, check if port is listening
   lsof -i :8080
   ```

4. **Restart dashboard:**
   ```bash
   ./claude-loop.sh dashboard stop
   ./claude-loop.sh dashboard start
   ```

### Authentication Failed

**Problem**: "Invalid authentication token" error

**Solutions:**

1. **Get correct token:**
   ```bash
   cat .claude-loop/dashboard/auth_token.txt
   ```

2. **Generate new token:**
   ```bash
   ./claude-loop.sh dashboard generate-token
   ```

3. **Clear browser cache:**
   ```javascript
   // In console
   localStorage.removeItem('auth_token');
   location.reload();
   ```

4. **Check for typos:**
   - Token is case-sensitive
   - No spaces before/after token

### No Stories Showing

**Problem**: Dashboard loads but story grid is empty

**Causes & Solutions:**

1. **No execution started:**
   - Start an execution: `./claude-loop.sh --prd prd.json`
   - Or submit to daemon: `./claude-loop.sh daemon submit prd.json`

2. **No prd.json file:**
   - Check current directory has `prd.json`
   - Or specify different directory in execution

3. **PRD not loaded yet:**
   - Wait a few seconds for execution to start
   - Check logs tab for activity

### Logs Not Streaming

**Problem**: Log entries not appearing or stopped updating

**Solutions:**

1. **Check SSE connection:**
   - Look at connection status indicator (top right)
   - Should show "Connected" (green)

2. **Check browser console:**
   - Press F12 → Console tab
   - Look for SSE errors or CORS errors

3. **Disable ad blocker:**
   - Some ad blockers interfere with EventSource
   - Whitelist `localhost:8080`

4. **Try different browser:**
   - Test in Chrome, Firefox, or Safari
   - Verify browser supports EventSource API

### High CPU or Memory Usage

**Problem**: Browser tab consuming excessive resources

**Solutions:**

1. **Increase refresh rate:**
   - Settings → Refresh Rate → 10 seconds
   - Reduces polling frequency

2. **Clear logs:**
   - Click "Clear" in logs tab
   - Large log buffers use more memory

3. **Close other tabs:**
   - Dashboard UI is JavaScript-intensive
   - Close unused browser tabs

4. **Disable animations:**
   ```css
   /* In browser DevTools → Elements → Styles */
   * { animation: none !important; }
   ```

### Dark Mode Not Working

**Problem**: Dark mode toggle doesn't change theme

**Solutions:**

1. **Check browser compatibility:**
   - CSS custom properties required (all modern browsers)

2. **Clear browser cache:**
   - Cmd+Shift+R / Ctrl+Shift+F5

3. **Manual toggle:**
   ```javascript
   // In console
   document.body.classList.add('dark-mode');
   localStorage.setItem('theme', 'dark');
   ```

### Dashboard Not Accessible Remotely

**Problem**: Cannot access dashboard from another machine

**Solutions:**

1. **Start with correct host:**
   ```bash
   ./claude-loop.sh dashboard start --host 0.0.0.0
   ```

2. **Check firewall:**
   ```bash
   # Allow port 8080
   # macOS: System Preferences → Security → Firewall
   # Linux: sudo ufw allow 8080
   ```

3. **Find correct IP:**
   ```bash
   # macOS/Linux
   ifconfig | grep "inet "

   # Windows
   ipconfig
   ```

4. **Use IP instead of localhost:**
   - Not: `http://localhost:8080`
   - Use: `http://192.168.1.100:8080` (your IP)

---

## Advanced Usage

### Viewing Daemon Queue in Dashboard

The dashboard can show daemon queue status:

**API Endpoint:**
```
GET /api/daemon/status
GET /api/daemon/queue
```

**Planned UI Feature:**
- Additional tab showing daemon queue
- Submit tasks directly from UI
- Cancel pending tasks from UI

### Monitoring Multiple Executions

Currently, the dashboard shows the most recent execution. To monitor multiple:

1. **Start separate dashboard instances:**
   ```bash
   # Terminal 1
   cd project1 && ./claude-loop.sh dashboard start --port 8080

   # Terminal 2
   cd project2 && ./claude-loop.sh dashboard start --port 8081
   ```

2. **Open multiple browser tabs:**
   - Tab 1: `http://localhost:8080`
   - Tab 2: `http://localhost:8081`

### Embedding in Existing Web Apps

The dashboard API can be consumed by your own web applications:

```javascript
// Fetch current status
const response = await fetch('http://localhost:8080/api/status', {
  headers: {
    'Authorization': `Bearer ${token}`
  }
});
const data = await response.json();

// Connect to SSE stream
const eventSource = new EventSource(
  `http://localhost:8080/api/stream?token=${token}`
);
eventSource.onmessage = (event) => {
  const update = JSON.parse(event.data);
  console.log('Status update:', update);
};
```

### Exporting Data

**Export Logs:**
```javascript
// In browser console
const logs = document.querySelectorAll('.log-entry');
const logText = Array.from(logs).map(l => l.textContent).join('\n');
console.log(logText);
// Copy from console
```

**Export Metrics:**
```bash
# Via API
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8080/api/metrics > metrics.json
```

---

## Best Practices

### 1. Keep Dashboard Running

Start the dashboard before beginning work:

```bash
# Add to your shell startup script
./claude-loop.sh dashboard start 2>/dev/null
```

### 2. Set Realistic Budget Limits

Configure budget based on your usage:

```
Small PRD (3-5 stories): $5-10
Medium PRD (6-10 stories): $10-20
Large PRD (10+ stories): $20-50
```

### 3. Use Browser Notifications

Enable notifications for long-running tasks:
- You can work on other things
- Get notified when execution completes
- No need to check dashboard constantly

### 4. Monitor Costs Regularly

Check Cost Tracker tab to:
- Understand which stories are expensive
- Optimize prompts for cost efficiency
- Track spending over time

### 5. Clear Logs Periodically

Large log buffers slow down the browser:
- Click "Clear" after reviewing logs
- Logs are preserved in files on disk

### 6. Use Dark Mode for Long Sessions

Easier on the eyes during extended use:
- Toggle moon icon (🌙) in top right
- Reduces eye strain
- Better for low-light environments

---

## Next Steps

- **Learn Daemon Mode**: [Daemon Mode Tutorial](./daemon-mode.md)
- **Try Quick Tasks**: [Quick Task Tutorial](./quick-task-tutorial.md)
- **API Reference**: [Dashboard API Docs](../api/dashboard-api.md)
- **Phase 2 Features**: [Phase 2 Documentation](../phase2/README.md)

---

## See Also

- [Dashboard UI Documentation](../features/dashboard-ui.md)
- [Dashboard API Reference](../api/dashboard-api.md)
- [CLI Reference](../reference/cli-reference.md)
- [Troubleshooting Guide](../troubleshooting/phase2-troubleshooting.md)
