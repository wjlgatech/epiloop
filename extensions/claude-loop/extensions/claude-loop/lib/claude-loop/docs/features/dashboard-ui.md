# Visual Progress Dashboard - Frontend UI

## Overview

The Visual Progress Dashboard UI is a responsive web-based interface for monitoring claude-loop execution progress in real-time. Built with vanilla JavaScript and modern CSS, it provides live updates via Server-Sent Events (SSE) and comprehensive visualization of story completion, logs, costs, and file changes.

**Version**: 1.0.0
**Status**: Production Ready
**Browser Support**: Chrome 90+, Firefox 88+, Safari 14+, Edge 90+

---

## Table of Contents

1. [Features](#features)
2. [Getting Started](#getting-started)
3. [UI Components](#ui-components)
4. [Real-time Updates](#real-time-updates)
5. [Mobile Support](#mobile-support)
6. [Settings](#settings)
7. [Browser Compatibility](#browser-compatibility)
8. [Troubleshooting](#troubleshooting)

---

## Features

### ✅ Live Execution View
- Current story being executed with title and ID
- Progress bar showing completion percentage
- Elapsed time counter (auto-updating)
- Running cost tracker with budget alerts

### ✅ Story Status Grid
- Visual grid displaying all stories with color-coded status:
  - **Green**: Complete
  - **Yellow**: In Progress (animated pulse)
  - **Gray**: Pending
- Click on story cards to view details
- Responsive grid layout (1-4 columns based on screen size)

### ✅ Real-time Logs Viewer
- Live streaming logs with color-coded message types:
  - **Info**: Gray
  - **Success**: Green
  - **Warning**: Yellow
  - **Error**: Red
- Auto-scroll to latest entries (toggleable)
- Clear logs button
- Monospace font for easy reading
- 1000-entry history limit

### ✅ Cost Tracker
- Total cost with currency formatting
- Input/output token counts
- Budget remaining indicator
- Cost breakdown by story
- Budget alert notifications

### ✅ File Changes Viewer
- List of modified files with paths
- Addition/deletion counts per file
- Click to view diff (planned)
- File count summary

### ✅ Execution History
- List of past runs with:
  - Run ID
  - Timestamp
  - Stories completed count
  - Duration
  - Total cost
- Click to load historical run data
- Refresh button for latest history

### ✅ Dark Mode
- Toggle between light and dark themes
- Smooth transitions
- Persists across sessions
- Accessible color contrast

### ✅ Settings Panel
- Refresh rate configuration (1-60 seconds)
- Budget limit setting
- Browser notifications toggle
- Sound notifications toggle
- Slide-in panel with overlay

### ✅ Control Buttons
- Pause execution (requires backend support)
- Stop execution (requires backend support)
- Currently disabled (backend integration pending)

---

## Getting Started

### Prerequisites

1. **Dashboard Backend Running**:
   ```bash
   ./claude-loop.sh dashboard start
   ```

2. **Authentication Token**:
   - Token auto-generated on first start
   - Located at `.claude-loop/dashboard/auth_token.txt`
   - Or generate manually:
     ```bash
     ./claude-loop.sh dashboard generate-token
     ```

### Accessing the Dashboard

1. **Open in Browser**:
   ```
   http://localhost:8080
   ```

2. **Enter Authentication Token**:
   - On first visit, you'll be prompted for the token
   - Copy from `.claude-loop/dashboard/auth_token.txt`
   - Token is saved in browser localStorage

3. **Dashboard Loads**:
   - Connection status shows "Connected" (green dot)
   - Data loads automatically
   - Real-time updates begin

### Custom Port

If running on a custom port:

```bash
# Start on port 9000
./claude-loop.sh dashboard start --port 9000

# Access at:
http://localhost:9000
```

---

## UI Components

### Header

```
┌─────────────────────────────────────────────────────────┐
│ 🔄 Claude Loop Dashboard    [Connected]  [🌙] [⚙️]     │
└─────────────────────────────────────────────────────────┘
```

**Components**:
- **Title**: Branding and identification
- **Connection Status**: Real-time connection indicator
- **Theme Toggle**: Switch between light/dark modes
- **Settings Button**: Open settings panel

### Live Execution Section

```
┌─ Live Execution ─────────────────── [Pause] [Stop] ─┐
│                                                       │
│  Current Story        Progress         Elapsed Time  │
│  US-001: Title       [████░░] 75%     12m 34s        │
│                                                       │
│  Running Cost                                         │
│  $1.23                                                │
└───────────────────────────────────────────────────────┘
```

**Features**:
- Real-time updates every 2 seconds (configurable)
- Animated progress bar
- Formatted time display (s/m/h)
- Currency formatting for cost
- Control buttons (pause/stop)

### Story Grid

```
┌─ Story Status ─────────────────── ● Complete ● In Progress ● Pending ─┐
│                                                                         │
│  ┌─ US-001 ──── Complete ┐  ┌─ US-002 ── In Progress ┐  ┌─ US-003 ── Pending ┐
│  │ Title                  │  │ Title                   │  │ Title               │
│  │ Description...         │  │ Description...          │  │ Description...      │
│  └────────────────────────┘  └─────────────────────────┘  └─────────────────────┘
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Status Colors**:
- **Complete**: Green border, solid
- **In Progress**: Yellow border, pulsing animation
- **Pending**: Gray border, semi-transparent

**Interactions**:
- Click to view story details
- Hover for elevation effect
- Responsive grid (1-4 columns)

### Tabs Section

```
┌─ [Logs] [Cost Tracker] [File Changes] [History] ─┐
│                                                    │
│  Tab Content Here                                  │
│                                                    │
└────────────────────────────────────────────────────┘
```

#### Logs Tab

```
┌─ Real-time Logs ─────────────── [Clear] [Auto-scroll: ON] ─┐
│                                                              │
│  [00:12:34] Starting execution                              │
│  [00:12:35] Story US-001 complete                           │
│  [00:12:36] Running tests...                                │
│  [00:12:37] Error: test failed                              │
│  [00:12:38] Retrying...                                     │
│  ...                                                         │
└──────────────────────────────────────────────────────────────┘
```

**Features**:
- Monospace font for alignment
- Color-coded message types
- Auto-scroll toggle
- Clear logs button
- 400px fixed height with scrollbar

#### Cost Tracker Tab

```
┌─ Cost Tracker ───────────────────────────────────┐
│                                                   │
│  ⚠️ Budget exceeded! Current: $12.34 / Limit: $10.00  │
│                                                   │
│  Total Cost      Input Tokens    Output Tokens   │
│  $12.34          150,000         45,000          │
│                                                   │
│  Budget Remaining                                 │
│  -$2.34                                           │
│                                                   │
│  Cost by Story                                    │
│  ┌────────────────────────────────┐              │
│  │ US-001    $0.45                │              │
│  │ US-002    $1.23                │              │
│  │ US-003    $2.34                │              │
│  └────────────────────────────────┘              │
└───────────────────────────────────────────────────┘
```

**Features**:
- Budget alert banner (when exceeded)
- Token counts with comma formatting
- Per-story cost breakdown
- Negative budget shown in red

#### File Changes Tab

```
┌─ File Changes ─────────── 12 files modified ─┐
│                                               │
│  lib/monitoring.sh                 +45 -12   │
│  claude-loop.sh                    +23 -5    │
│  docs/features/new-feature.md      +150 -0   │
│  ...                                          │
└───────────────────────────────────────────────┘
```

**Features**:
- File path in monospace font
- Addition/deletion counts
- Click to view diff (planned)
- Scrollable list

#### History Tab

```
┌─ Execution History ────────────── [Refresh] ─┐
│                                               │
│  20260113_140523                              │
│  2026-01-13 14:05:23                          │
│  Stories: 5/10  Duration: 45m  Cost: $3.21   │
│                                               │
│  20260113_100015                              │
│  2026-01-13 10:00:15                          │
│  Stories: 10/10  Duration: 1h 23m  Cost: $5.67│
│  ...                                          │
└───────────────────────────────────────────────┘
```

**Features**:
- Chronological list (newest first)
- Run ID, timestamp, stats
- Click to load run details
- Refresh button

### Settings Panel

```
┌─ Settings ──────────────────────── [×] ─┐
│                                          │
│  Refresh Rate (seconds)                  │
│  [2]                                     │
│  How often to update data (1-60 seconds) │
│                                          │
│  Budget Limit ($)                        │
│  [10.00]                                 │
│  Alert when cost exceeds this amount     │
│                                          │
│  ☑ Enable Browser Notifications         │
│                                          │
│  ☐ Play Sound on Completion             │
│                                          │
│  [Save Settings]                         │
└──────────────────────────────────────────┘
```

**Configuration Options**:
- **Refresh Rate**: 1-60 seconds (default: 2)
- **Budget Limit**: Dollar amount for alerts (default: $10.00)
- **Browser Notifications**: Toggle browser notifications
- **Sound**: Play completion sound (requires audio file)

**Persistence**:
- Settings saved to localStorage
- Persists across browser sessions
- Reloads on page refresh

---

## Real-time Updates

### Server-Sent Events (SSE)

The dashboard uses SSE for real-time updates from the backend:

```javascript
// Connection established
EventSource: http://localhost:8080/api/stream

// Events received:
{
  "type": "status_update",
  "data": { ... },
  "timestamp": "2026-01-13T14:00:00Z"
}
```

**Event Types**:
- `connected`: Initial connection established
- `status_update`: Execution status changed
- `story_update`: Story status changed
- `log`: New log entry
- `metrics_update`: Metrics updated

**Reconnection**:
- Automatic reconnection on connection loss
- 5-second retry delay
- Connection status indicator updates
- Warning log entry on disconnect

### Polling Fallback

In addition to SSE, the dashboard polls the API every 2 seconds (configurable):

```javascript
setInterval(() => {
  loadDashboardData();
}, CONFIG.refreshRate);
```

**Why Both?**:
- SSE for immediate updates
- Polling ensures data freshness if SSE fails
- Redundancy for reliability

---

## Mobile Support

### Responsive Design

The dashboard is fully responsive and mobile-friendly:

**Desktop (> 768px)**:
- 4-column story grid
- 4-column execution status
- Side-by-side layouts

**Tablet (768px - 480px)**:
- 2-column story grid
- 2-column execution status
- Stacked layouts

**Mobile (< 480px)**:
- 1-column story grid
- 1-column execution status
- Full-width settings panel
- Horizontal tab scroll

### Touch Interactions

- Tap to select tabs
- Swipe to scroll logs/history
- Pinch to zoom on file diffs
- Pull to refresh (browser default)

### Performance Optimization

- Lazy loading of history
- Virtual scrolling for large lists
- Throttled animations
- Minimal re-renders

---

## Settings

### Configuration Options

#### Refresh Rate

**Range**: 1-60 seconds
**Default**: 2 seconds
**Impact**: Higher values reduce server load, lower values increase responsiveness

```javascript
CONFIG.refreshRate = 2000; // milliseconds
```

#### Budget Limit

**Default**: $10.00
**Purpose**: Show alert when execution cost exceeds limit

```javascript
CONFIG.budgetLimit = 10.00; // dollars
```

**Alert Behavior**:
- Banner appears in Cost Tracker tab
- Browser notification (if enabled)
- Sound alert (if enabled)

#### Browser Notifications

**Default**: Enabled
**Requires**: Browser permission

**Triggers**:
- Budget exceeded
- Execution complete
- Execution failed

**Setup**:
```javascript
// Request permission
Notification.requestPermission();

// Send notification
new Notification('Budget Alert', {
  body: 'Cost exceeded $10.00',
  icon: '/favicon.ico'
});
```

#### Sound Notifications

**Default**: Disabled
**Requires**: Audio file (not included)

**Planned Implementation**:
```javascript
const audio = new Audio('/sounds/notification.mp3');
audio.play();
```

### Persistence

All settings are stored in browser localStorage:

```javascript
localStorage.setItem('dashboard-config', JSON.stringify(CONFIG));
```

**Stored Data**:
- `refreshRate`: Number
- `budgetLimit`: Number
- `notificationsEnabled`: Boolean
- `soundEnabled`: Boolean
- `authToken`: String
- `theme`: String (light/dark)

---

## Browser Compatibility

### Supported Browsers

| Browser | Minimum Version | Notes |
|---------|----------------|-------|
| Chrome | 90+ | Full support |
| Firefox | 88+ | Full support |
| Safari | 14+ | Full support |
| Edge | 90+ | Full support |
| Opera | 76+ | Full support |

### Required Features

- **ES6 JavaScript**: Arrow functions, template literals, destructuring
- **CSS Grid**: Story grid layout
- **CSS Custom Properties**: Theme variables
- **Fetch API**: API requests
- **EventSource**: Server-Sent Events
- **localStorage**: Settings persistence

### Polyfills

Not required for supported browsers. For older browsers, consider:

```html
<script src="https://polyfill.io/v3/polyfill.min.js"></script>
```

---

## Troubleshooting

### Connection Issues

#### "Failed to connect to dashboard API"

**Causes**:
- Dashboard server not running
- Wrong port number
- Invalid authentication token

**Solutions**:
1. Check server is running:
   ```bash
   ./claude-loop.sh dashboard status
   ```

2. Verify port:
   ```bash
   ./claude-loop.sh dashboard start --port 8080
   ```

3. Check token:
   ```bash
   cat .claude-loop/dashboard/auth_token.txt
   ```

4. Regenerate token:
   ```bash
   ./claude-loop.sh dashboard generate-token
   ```

#### "Connection lost, reconnecting..."

**Causes**:
- Network interruption
- Server crashed
- Server restarted

**Solutions**:
- Wait for automatic reconnection (5 seconds)
- Refresh browser page
- Restart dashboard server

### Display Issues

#### Stories Not Showing

**Causes**:
- No prd.json file
- No execution started
- API error

**Solutions**:
1. Check prd.json exists
2. Start an execution
3. Check browser console for errors

#### Logs Not Streaming

**Causes**:
- SSE connection failed
- Ad blocker blocking EventSource
- CORS issue

**Solutions**:
1. Check browser console for SSE errors
2. Disable ad blocker
3. Check server CORS configuration

#### Theme Not Persisting

**Causes**:
- localStorage disabled
- Private browsing mode
- Storage quota exceeded

**Solutions**:
1. Enable localStorage in browser settings
2. Exit private browsing
3. Clear localStorage to free space

### Performance Issues

#### Slow Loading

**Causes**:
- Large history (100+ runs)
- Many files changed (1000+)
- Slow network

**Solutions**:
1. Increase refresh rate in settings
2. Clear browser cache
3. Restart browser

#### High CPU Usage

**Causes**:
- Too many logs (10,000+)
- Rapid SSE updates
- Animations on low-end devices

**Solutions**:
1. Clear logs regularly
2. Increase refresh rate
3. Disable animations (CSS media query)

---

## API Integration

### Authentication

```javascript
// Add token to all requests
headers: {
  'Authorization': `Bearer ${token}`,
  'Content-Type': 'application/json'
}
```

### Endpoints Used

| Endpoint | Purpose | Frequency |
|----------|---------|-----------|
| `/api/status` | Current execution status | Every 2s |
| `/api/stories` | Story list with status | Every 2s |
| `/api/logs` | Execution logs | On demand |
| `/api/metrics` | Token usage and cost | Every 2s |
| `/api/history` | Past runs | On demand |
| `/api/stream` | SSE real-time updates | Persistent |

### Error Handling

```javascript
try {
  const data = await api.fetch('/api/status');
} catch (error) {
  console.error('API Error:', error);
  addLogEntry(`Error: ${error.message}`, 'error');
}
```

---

## Customization

### Theming

Modify CSS custom properties in `styles.css`:

```css
:root {
  --accent-primary: #007bff;  /* Change primary color */
  --bg-primary: #ffffff;      /* Background color */
  --text-primary: #212529;    /* Text color */
}
```

### Adding Custom Tabs

1. Add tab button to HTML:
```html
<button class="tab-btn" data-tab="custom">Custom</button>
```

2. Add tab content:
```html
<div class="tab-content" id="custom-tab">
  <!-- Your content here -->
</div>
```

3. Tab switching is automatic.

### Extending Functionality

Add custom event handlers in `app.js`:

```javascript
function initializeEventHandlers() {
  // Add your handlers here
  document.getElementById('my-button').addEventListener('click', () => {
    // Custom logic
  });
}
```

---

## Future Enhancements

### Planned Features

1. **File Diff Viewer**:
   - Inline diff display
   - Syntax highlighting
   - Side-by-side comparison

2. **Control Buttons**:
   - Pause/resume execution
   - Stop execution
   - Skip current story

3. **Advanced Filters**:
   - Filter stories by status
   - Filter logs by level
   - Search logs by keyword

4. **Export Functionality**:
   - Export logs to file
   - Export metrics to CSV
   - Generate PDF report

5. **Collaborative Features**:
   - Multi-user support
   - Real-time cursors
   - Comments on stories

6. **Analytics Dashboard**:
   - Cost trends over time
   - Success rate charts
   - Performance metrics

---

## Contributing

### Development Setup

1. **Prerequisites**:
   - Python 3.8+
   - Flask and flask-cors
   - Modern web browser

2. **Start Dashboard**:
   ```bash
   ./claude-loop.sh dashboard start --debug
   ```

3. **Edit Files**:
   - HTML: `lib/dashboard/static/index.html`
   - CSS: `lib/dashboard/static/styles.css`
   - JS: `lib/dashboard/static/app.js`

4. **Test Changes**:
   - Refresh browser (Cmd+R / Ctrl+R)
   - Check browser console for errors

### Code Style

- **HTML**: Semantic HTML5, accessibility attributes
- **CSS**: BEM naming, CSS custom properties, mobile-first
- **JavaScript**: ES6+, functional style, JSDoc comments

### Testing

- **Manual Testing**: Test all features in all supported browsers
- **Responsive Testing**: Test on mobile, tablet, desktop sizes
- **Performance Testing**: Check CPU/memory usage with large datasets

---

## Changelog

### Version 1.0.0 (2026-01-13)

**Initial Release**

Features:
- Live execution view with progress tracking
- Story status grid with color-coding
- Real-time logs viewer with auto-scroll
- Cost tracker with budget alerts
- File changes viewer
- Execution history
- Dark mode support
- Settings panel
- SSE real-time updates
- Mobile-responsive design
- Browser notifications
- localStorage persistence

---

## License

Part of the Claude Loop project. See main LICENSE file.

---

## Support

For issues and questions:
- GitHub Issues: [claude-loop/issues](https://github.com/yourusername/claude-loop/issues)
- Documentation: [docs/](../README.md)
- Discord: [claude-loop community](https://discord.gg/yourserver)

---

## Acknowledgments

- Flask framework for backend API
- CSS Grid and Flexbox for responsive layout
- Server-Sent Events for real-time updates
- Claude AI for code generation and assistance
