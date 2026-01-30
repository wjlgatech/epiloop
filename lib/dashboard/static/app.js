/**
 * Claude Loop Dashboard - Frontend Application
 *
 * Connects to the Dashboard Backend API for real-time progress monitoring.
 * Features: SSE streaming, story grid, logs viewer, cost tracking, file changes, history.
 */

// ============================================================================
// Configuration
// ============================================================================

const CONFIG = {
    apiUrl: 'http://localhost:8080',
    authToken: null,
    refreshRate: 2000, // milliseconds
    budgetLimit: 10.00, // dollars
    notificationsEnabled: true,
    soundEnabled: false,
    autoScroll: true
};

// Load config from localStorage
function loadConfig() {
    const saved = localStorage.getItem('dashboard-config');
    if (saved) {
        try {
            const parsed = JSON.parse(saved);
            Object.assign(CONFIG, parsed);
        } catch (e) {
            console.error('Failed to load config:', e);
        }
    }
}

function saveConfig() {
    localStorage.setItem('dashboard-config', JSON.stringify(CONFIG));
}

// ============================================================================
// State Management
// ============================================================================

const STATE = {
    connected: false,
    currentRun: null,
    stories: [],
    logs: [],
    metrics: {},
    history: [],
    eventSource: null
};

// ============================================================================
// API Client
// ============================================================================

class DashboardAPI {
    constructor(baseUrl, token) {
        this.baseUrl = baseUrl;
        this.token = token;
    }

    async fetch(endpoint, options = {}) {
        const headers = {
            'Authorization': `Bearer ${this.token}`,
            'Content-Type': 'application/json',
            ...options.headers
        };

        const response = await fetch(`${this.baseUrl}${endpoint}`, {
            ...options,
            headers
        });

        if (!response.ok) {
            const error = await response.json().catch(() => ({ error: 'Unknown error' }));
            throw new Error(error.error || `HTTP ${response.status}`);
        }

        return await response.json();
    }

    async getStatus() {
        return await this.fetch('/api/status');
    }

    async getStories(runId = null) {
        const query = runId ? `?run_id=${runId}` : '';
        return await this.fetch(`/api/stories${query}`);
    }

    async getLogs(runId = null, limit = 100, offset = 0) {
        const params = new URLSearchParams({ limit, offset });
        if (runId) params.append('run_id', runId);
        return await this.fetch(`/api/logs?${params}`);
    }

    async getMetrics(runId = null) {
        const query = runId ? `?run_id=${runId}` : '';
        return await this.fetch(`/api/metrics${query}`);
    }

    async getHistory(limit = 20, offset = 0) {
        const params = new URLSearchParams({ limit, offset });
        return await this.fetch(`/api/history?${params}`);
    }

    createEventSource() {
        const eventSource = new EventSource(`${this.baseUrl}/api/stream`, {
            withCredentials: false
        });

        // Note: EventSource doesn't support custom headers, so we need to pass token via URL
        // For production, consider using WebSocket with custom authentication
        return eventSource;
    }
}

let api = null;

// ============================================================================
// Authentication
// ============================================================================

function promptForToken() {
    const token = prompt('Enter dashboard authentication token:');
    if (token) {
        CONFIG.authToken = token;
        saveConfig();
        return true;
    }
    return false;
}

function checkAuthentication() {
    if (!CONFIG.authToken) {
        if (!promptForToken()) {
            showError('Authentication required to use the dashboard.');
            return false;
        }
    }
    return true;
}

// ============================================================================
// UI Updates
// ============================================================================

function updateConnectionStatus(connected, message = '') {
    const statusEl = document.getElementById('connection-status');
    const textEl = statusEl.querySelector('.status-text');

    if (connected) {
        statusEl.classList.add('connected');
        statusEl.classList.remove('error');
        textEl.textContent = 'Connected';
    } else if (message) {
        statusEl.classList.add('error');
        statusEl.classList.remove('connected');
        textEl.textContent = message;
    } else {
        statusEl.classList.remove('connected', 'error');
        textEl.textContent = 'Connecting...';
    }
}

function updateExecutionStatus(status) {
    const currentStoryEl = document.getElementById('current-story');
    const progressEl = document.getElementById('progress-percent');
    const progressFillEl = document.getElementById('progress-fill');
    const elapsedEl = document.getElementById('elapsed-time');
    const costEl = document.getElementById('running-cost');

    if (status && status.current_story) {
        currentStoryEl.textContent = `${status.current_story.id}: ${status.current_story.title}`;
    } else {
        currentStoryEl.textContent = 'No active execution';
    }

    const progress = status?.progress_percent || 0;
    progressEl.textContent = `${progress}%`;
    progressFillEl.style.width = `${progress}%`;

    if (status?.elapsed_time_ms) {
        const seconds = Math.floor(status.elapsed_time_ms / 1000);
        const minutes = Math.floor(seconds / 60);
        const hours = Math.floor(minutes / 60);

        if (hours > 0) {
            elapsedEl.textContent = `${hours}h ${minutes % 60}m`;
        } else if (minutes > 0) {
            elapsedEl.textContent = `${minutes}m ${seconds % 60}s`;
        } else {
            elapsedEl.textContent = `${seconds}s`;
        }
    } else {
        elapsedEl.textContent = '0s';
    }

    const cost = status?.total_cost || 0;
    costEl.textContent = `$${cost.toFixed(2)}`;

    // Budget alert
    if (cost > CONFIG.budgetLimit) {
        showBudgetAlert(cost);
    }
}

function updateStoryGrid(stories) {
    const gridEl = document.getElementById('story-grid');

    if (!stories || stories.length === 0) {
        gridEl.innerHTML = '<div class="empty-state">No stories found</div>';
        return;
    }

    gridEl.innerHTML = stories.map(story => {
        const status = story.passes ? 'complete' : (story.in_progress ? 'in-progress' : 'pending');
        const statusLabel = story.passes ? 'Complete' : (story.in_progress ? 'In Progress' : 'Pending');

        return `
            <div class="story-card status-${status}" data-story-id="${story.id}">
                <div class="story-header">
                    <div class="story-id">${story.id}</div>
                    <div class="story-status-badge ${status}">${statusLabel}</div>
                </div>
                <div class="story-title">${story.title}</div>
                <div class="story-description">${story.description || ''}</div>
            </div>
        `;
    }).join('');

    // Add click handlers
    gridEl.querySelectorAll('.story-card').forEach(card => {
        card.addEventListener('click', () => {
            const storyId = card.dataset.storyId;
            const story = stories.find(s => s.id === storyId);
            if (story) {
                showStoryDetails(story);
            }
        });
    });
}

function showStoryDetails(story) {
    const details = `
Story: ${story.id}
Title: ${story.title}
Description: ${story.description || 'N/A'}
Priority: ${story.priority}
Status: ${story.passes ? 'Complete' : 'Pending'}
Notes: ${story.notes || 'None'}
    `.trim();

    alert(details);
}

function addLogEntry(message, type = 'info') {
    const logsEl = document.getElementById('logs-viewer');
    const timestamp = new Date().toLocaleTimeString();

    const entry = document.createElement('div');
    entry.className = `log-entry log-${type}`;
    entry.innerHTML = `
        <span class="log-timestamp">[${timestamp}]</span>
        <span class="log-message">${escapeHtml(message)}</span>
    `;

    logsEl.appendChild(entry);

    // Auto-scroll to bottom if enabled
    if (CONFIG.autoScroll) {
        logsEl.scrollTop = logsEl.scrollHeight;
    }

    // Keep only last 1000 entries
    while (logsEl.children.length > 1000) {
        logsEl.removeChild(logsEl.firstChild);
    }
}

function clearLogs() {
    const logsEl = document.getElementById('logs-viewer');
    logsEl.innerHTML = '';
    addLogEntry('Logs cleared', 'info');
}

function updateCostTracker(metrics) {
    document.getElementById('total-cost').textContent = `$${(metrics.total_cost || 0).toFixed(2)}`;
    document.getElementById('input-tokens').textContent = (metrics.total_input_tokens || 0).toLocaleString();
    document.getElementById('output-tokens').textContent = (metrics.total_output_tokens || 0).toLocaleString();

    const remaining = CONFIG.budgetLimit - (metrics.total_cost || 0);
    document.getElementById('budget-remaining').textContent = `$${remaining.toFixed(2)}`;

    // Update cost by story
    const costByStoryEl = document.getElementById('cost-by-story');
    if (metrics.iterations && metrics.iterations.length > 0) {
        costByStoryEl.innerHTML = metrics.iterations.map(iter => `
            <div class="cost-story-item">
                <span>${iter.story_id}</span>
                <span>$${(iter.cost || 0).toFixed(3)}</span>
            </div>
        `).join('');
    } else {
        costByStoryEl.innerHTML = '<div class="empty-state">No cost data yet</div>';
    }
}

function showBudgetAlert(cost) {
    const alertEl = document.getElementById('budget-alert');
    const textEl = document.getElementById('budget-alert-text');

    alertEl.style.display = 'flex';
    textEl.textContent = `Budget exceeded! Current: $${cost.toFixed(2)} / Limit: $${CONFIG.budgetLimit.toFixed(2)}`;

    // Send browser notification if enabled
    if (CONFIG.notificationsEnabled && 'Notification' in window && Notification.permission === 'granted') {
        new Notification('Budget Alert', {
            body: `Dashboard cost has exceeded $${CONFIG.budgetLimit.toFixed(2)}`,
            icon: '/favicon.ico'
        });
    }
}

function updateFileChanges(files) {
    const filesEl = document.getElementById('files-list');
    const countEl = document.getElementById('files-modified-count');

    if (!files || files.length === 0) {
        filesEl.innerHTML = '<div class="empty-state">No file changes yet</div>';
        countEl.textContent = '0 files modified';
        return;
    }

    countEl.textContent = `${files.length} file${files.length > 1 ? 's' : ''} modified`;

    filesEl.innerHTML = files.map(file => `
        <div class="file-item" data-file-path="${file.path}">
            <div class="file-path">${file.path}</div>
            <div class="file-stats">
                +${file.additions || 0} -${file.deletions || 0}
            </div>
        </div>
    `).join('');
}

function updateHistory(history) {
    const historyEl = document.getElementById('history-list');

    if (!history || history.length === 0) {
        historyEl.innerHTML = '<div class="empty-state">No execution history</div>';
        return;
    }

    historyEl.innerHTML = history.map(run => {
        const timestamp = new Date(run.timestamp).toLocaleString();
        const duration = formatDuration(run.duration_ms);

        return `
            <div class="history-item" data-run-id="${run.run_id}">
                <div class="history-header-row">
                    <div class="history-run-id">${run.run_id}</div>
                    <div class="history-timestamp">${timestamp}</div>
                </div>
                <div class="history-stats">
                    <div class="history-stat">
                        <span class="history-stat-label">Stories:</span>
                        <span class="history-stat-value">${run.stories_completed || 0}/${run.total_stories || 0}</span>
                    </div>
                    <div class="history-stat">
                        <span class="history-stat-label">Duration:</span>
                        <span class="history-stat-value">${duration}</span>
                    </div>
                    <div class="history-stat">
                        <span class="history-stat-label">Cost:</span>
                        <span class="history-stat-value">$${(run.total_cost || 0).toFixed(2)}</span>
                    </div>
                </div>
            </div>
        `;
    }).join('');

    // Add click handlers
    historyEl.querySelectorAll('.history-item').forEach(item => {
        item.addEventListener('click', () => {
            const runId = item.dataset.runId;
            loadRunDetails(runId);
        });
    });
}

// ============================================================================
// Data Loading
// ============================================================================

async function loadDashboardData() {
    try {
        // Load status
        const status = await api.getStatus();
        updateExecutionStatus(status);

        // Load stories
        const stories = await api.getStories();
        STATE.stories = stories;
        updateStoryGrid(stories);

        // Load logs
        const logs = await api.getLogs();
        // Note: Logs are streamed via SSE, so we don't need to load them here

        // Load metrics
        const metrics = await api.getMetrics();
        STATE.metrics = metrics;
        updateCostTracker(metrics);

        // Load history
        const history = await api.getHistory();
        STATE.history = history;
        updateHistory(history);

    } catch (error) {
        console.error('Failed to load dashboard data:', error);
        addLogEntry(`Error loading data: ${error.message}`, 'error');
    }
}

async function loadRunDetails(runId) {
    try {
        const stories = await api.getStories(runId);
        const metrics = await api.getMetrics(runId);

        updateStoryGrid(stories);
        updateCostTracker(metrics);

        addLogEntry(`Loaded run: ${runId}`, 'success');
    } catch (error) {
        console.error('Failed to load run details:', error);
        addLogEntry(`Error loading run: ${error.message}`, 'error');
    }
}

// ============================================================================
// Server-Sent Events (SSE)
// ============================================================================

function connectSSE() {
    if (STATE.eventSource) {
        STATE.eventSource.close();
    }

    // Note: EventSource doesn't support custom headers, so authentication needs to be handled differently
    // For now, we'll use the token in the URL (not secure for production)
    const eventSource = new EventSource(`${CONFIG.apiUrl}/api/stream?token=${CONFIG.authToken}`);

    eventSource.onopen = () => {
        STATE.connected = true;
        updateConnectionStatus(true);
        addLogEntry('Connected to server', 'success');
    };

    eventSource.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            handleSSEEvent(data);
        } catch (error) {
            console.error('Failed to parse SSE event:', error);
        }
    };

    eventSource.onerror = (error) => {
        console.error('SSE error:', error);
        STATE.connected = false;
        updateConnectionStatus(false, 'Connection lost');
        addLogEntry('Connection to server lost, reconnecting...', 'warning');

        // Reconnect after 5 seconds
        setTimeout(() => {
            if (!STATE.connected) {
                connectSSE();
            }
        }, 5000);
    };

    STATE.eventSource = eventSource;
}

function handleSSEEvent(event) {
    switch (event.type) {
        case 'connected':
            addLogEntry('Real-time updates connected', 'success');
            break;

        case 'status_update':
            if (event.data) {
                updateExecutionStatus(event.data);
            }
            break;

        case 'story_update':
            if (event.data && event.data.stories) {
                STATE.stories = event.data.stories;
                updateStoryGrid(event.data.stories);
            }
            break;

        case 'log':
            if (event.data && event.data.message) {
                addLogEntry(event.data.message, event.data.level || 'info');
            }
            break;

        case 'metrics_update':
            if (event.data) {
                STATE.metrics = event.data;
                updateCostTracker(event.data);
            }
            break;

        default:
            console.log('Unknown SSE event:', event);
    }
}

// ============================================================================
// Event Handlers
// ============================================================================

function initializeEventHandlers() {
    // Theme toggle
    document.getElementById('theme-toggle').addEventListener('click', () => {
        const html = document.documentElement;
        const currentTheme = html.getAttribute('data-theme') || 'light';
        const newTheme = currentTheme === 'light' ? 'dark' : 'light';
        html.setAttribute('data-theme', newTheme);
        localStorage.setItem('theme', newTheme);
    });

    // Settings
    document.getElementById('settings-btn').addEventListener('click', () => {
        document.getElementById('settings-panel').classList.add('active');
        document.getElementById('overlay').classList.add('active');
    });

    document.getElementById('close-settings').addEventListener('click', closeSettings);
    document.getElementById('overlay').addEventListener('click', closeSettings);

    document.getElementById('save-settings').addEventListener('click', () => {
        CONFIG.refreshRate = parseInt(document.getElementById('refresh-rate').value) * 1000;
        CONFIG.budgetLimit = parseFloat(document.getElementById('budget-limit').value);
        CONFIG.notificationsEnabled = document.getElementById('notifications-enabled').checked;
        CONFIG.soundEnabled = document.getElementById('sound-enabled').checked;

        saveConfig();
        closeSettings();
        addLogEntry('Settings saved', 'success');
    });

    // Control buttons
    document.getElementById('pause-btn').addEventListener('click', () => {
        addLogEntry('Pause functionality not yet implemented', 'warning');
    });

    document.getElementById('stop-btn').addEventListener('click', () => {
        addLogEntry('Stop functionality not yet implemented', 'warning');
    });

    // Tabs
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const tabName = btn.dataset.tab;
            switchTab(tabName);
        });
    });

    // Logs controls
    document.getElementById('clear-logs').addEventListener('click', clearLogs);

    document.getElementById('auto-scroll-toggle').addEventListener('click', (e) => {
        CONFIG.autoScroll = !CONFIG.autoScroll;
        e.target.textContent = `Auto-scroll: ${CONFIG.autoScroll ? 'ON' : 'OFF'}`;
        saveConfig();
    });

    // History refresh
    document.getElementById('refresh-history').addEventListener('click', async () => {
        const history = await api.getHistory();
        STATE.history = history;
        updateHistory(history);
        addLogEntry('History refreshed', 'success');
    });
}

function closeSettings() {
    document.getElementById('settings-panel').classList.remove('active');
    document.getElementById('overlay').classList.remove('active');
}

function switchTab(tabName) {
    // Update tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
        if (btn.dataset.tab === tabName) {
            btn.classList.add('active');
        }
    });

    // Update tab content
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
        if (content.id === `${tabName}-tab`) {
            content.classList.add('active');
        }
    });
}

// ============================================================================
// Utility Functions
// ============================================================================

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatDuration(ms) {
    const seconds = Math.floor(ms / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);

    if (hours > 0) {
        return `${hours}h ${minutes % 60}m`;
    } else if (minutes > 0) {
        return `${minutes}m ${seconds % 60}s`;
    } else {
        return `${seconds}s`;
    }
}

function showError(message) {
    addLogEntry(message, 'error');
    alert(message);
}

// ============================================================================
// Initialization
// ============================================================================

async function initialize() {
    // Load saved configuration
    loadConfig();

    // Load saved theme
    const savedTheme = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-theme', savedTheme);

    // Load settings into UI
    document.getElementById('refresh-rate').value = CONFIG.refreshRate / 1000;
    document.getElementById('budget-limit').value = CONFIG.budgetLimit;
    document.getElementById('notifications-enabled').checked = CONFIG.notificationsEnabled;
    document.getElementById('sound-enabled').checked = CONFIG.soundEnabled;

    // Check authentication
    if (!checkAuthentication()) {
        return;
    }

    // Initialize API client
    api = new DashboardAPI(CONFIG.apiUrl, CONFIG.authToken);

    // Initialize event handlers
    initializeEventHandlers();

    // Request notification permission
    if (CONFIG.notificationsEnabled && 'Notification' in window && Notification.permission === 'default') {
        Notification.requestPermission();
    }

    // Load initial data
    try {
        await loadDashboardData();
    } catch (error) {
        console.error('Failed to load initial data:', error);
        showError(`Failed to connect to dashboard API: ${error.message}\n\nPlease check that the dashboard server is running and the authentication token is correct.`);
        return;
    }

    // Connect SSE for real-time updates
    connectSSE();

    // Set up periodic refresh
    setInterval(async () => {
        if (STATE.connected) {
            try {
                await loadDashboardData();
            } catch (error) {
                console.error('Failed to refresh data:', error);
            }
        }
    }, CONFIG.refreshRate);

    addLogEntry('Dashboard initialized successfully', 'success');
}

// Start the application
document.addEventListener('DOMContentLoaded', initialize);
