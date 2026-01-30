# Dashboard API Documentation

## Overview

The Dashboard Backend API provides REST endpoints and real-time streaming for monitoring claude-loop execution progress. Built with Flask and Server-Sent Events (SSE), it enables web-based dashboards to track story completion, view logs, and monitor costs in real-time.

**Version**: 1.0.0
**Base URL**: `http://localhost:8080`
**Authentication**: Bearer Token

## Table of Contents

1. [Getting Started](#getting-started)
2. [Authentication](#authentication)
3. [Endpoints](#endpoints)
4. [Server-Sent Events (SSE)](#server-sent-events-sse)
5. [Data Models](#data-models)
6. [Error Handling](#error-handling)
7. [Examples](#examples)

---

## Getting Started

### Starting the Dashboard Server

```bash
# Start dashboard on default port 8080
./claude-loop.sh dashboard start

# Start on custom port
./claude-loop.sh dashboard start --port 9000

# Start on custom host (e.g., for remote access)
./claude-loop.sh dashboard start --host 0.0.0.0 --port 8080
```

### Stopping the Server

```bash
./claude-loop.sh dashboard stop
```

### Checking Status

```bash
./claude-loop.sh dashboard status
```

### Viewing Logs

```bash
./claude-loop.sh dashboard logs
```

---

## Authentication

All API endpoints (except `/api/health`) require authentication via Bearer token.

### Obtaining a Token

A token is automatically generated when the dashboard starts for the first time. You can also generate a new token:

```bash
./claude-loop.sh dashboard generate-token
```

The token is saved in `.claude-loop/dashboard/auth_token.txt`.

### Using the Token

Include the token in the `Authorization` header of all requests:

```bash
Authorization: Bearer <your-token-here>
```

**Example:**

```bash
curl -H "Authorization: Bearer abc123xyz" \
  http://localhost:8080/api/status
```

---

## Endpoints

### Health Check

**GET** `/api/health`

Health check endpoint (no authentication required).

**Response:**

```json
{
  "status": "ok",
  "timestamp": "2026-01-13T20:00:00Z",
  "version": "1.0.0"
}
```

**Status Codes:**

- `200 OK`: Server is healthy

---

### Get Current Status

**GET** `/api/status`

Get the current execution status.

**Authentication**: Required

**Response:**

```json
{
  "is_running": true,
  "run_id": "20260113_200000",
  "current_story": {
    "id": "US-207",
    "status": "in_progress",
    "elapsed_ms": 15000
  },
  "progress_pct": 60.0,
  "completed_stories": 6,
  "total_stories": 10,
  "elapsed_time": 3600,
  "estimated_remaining": 2400,
  "cost_so_far": 2.50,
  "last_update": "2026-01-13T20:00:00Z"
}
```

**Status Codes:**

- `200 OK`: Success
- `401 Unauthorized`: Missing or invalid token
- `500 Internal Server Error`: Server error

---

### Get Stories

**GET** `/api/stories`

Get all stories with their current status.

**Authentication**: Required

**Query Parameters:**

- `run_id` (optional): Specific run ID to query

**Response:**

```json
{
  "stories": [
    {
      "id": "US-201",
      "title": "Skills Architecture - Core Framework",
      "description": "Implement Cowork-style progressive disclosure...",
      "priority": 1,
      "status": "completed",
      "notes": "Implemented in commit c84897d",
      "estimatedComplexity": "medium",
      "dependencies": []
    },
    {
      "id": "US-207",
      "title": "Visual Progress Dashboard - Backend API",
      "description": "Create web-based dashboard backend...",
      "priority": 2,
      "status": "pending",
      "notes": "",
      "estimatedComplexity": "high",
      "dependencies": ["US-205"]
    }
  ],
  "total": 10,
  "completed": 6,
  "pending": 4
}
```

**Status Codes:**

- `200 OK`: Success
- `401 Unauthorized`: Missing or invalid token

---

### Get Logs

**GET** `/api/logs`

Get execution logs from progress.txt.

**Authentication**: Required

**Query Parameters:**

- `run_id` (optional): Specific run ID to query
- `limit` (optional, default: 100): Maximum number of log entries
- `offset` (optional, default: 0): Number of entries to skip (pagination)

**Response:**

```json
{
  "logs": [
    {
      "timestamp": "2026-01-13 14:40:00",
      "lines": [
        "**Story**: US-201 - Skills Architecture Core Framework",
        "**Status**: Complete",
        "**What was implemented**:",
        "- Created skills framework with three-layer architecture",
        "..."
      ]
    }
  ],
  "total": 50,
  "limit": 100,
  "offset": 0
}
```

**Status Codes:**

- `200 OK`: Success
- `401 Unauthorized`: Missing or invalid token

---

### Get Metrics

**GET** `/api/metrics`

Get execution metrics (tokens, cost, timing).

**Authentication**: Required

**Query Parameters:**

- `run_id` (optional): Specific run ID to query (defaults to most recent)

**Response:**

```json
{
  "elapsed_time_s": 3600,
  "total_cost": 2.50,
  "total_iterations": 10,
  "success_count": 9,
  "failure_count": 1,
  "last_update": "2026-01-13T20:00:00Z",
  "iterations": [
    {
      "story_id": "US-201",
      "status": "success",
      "elapsed_ms": 180000,
      "tokens_in": 5000,
      "tokens_out": 2000,
      "cost": 0.15,
      "agents_used": ["backend-architect"]
    }
  ]
}
```

**Status Codes:**

- `200 OK`: Success
- `401 Unauthorized`: Missing or invalid token
- `404 Not Found`: Metrics file not found

---

### Get History

**GET** `/api/history`

Get historical runs.

**Authentication**: Required

**Query Parameters:**

- `limit` (optional, default: 20): Maximum number of runs
- `offset` (optional, default: 0): Number of runs to skip (pagination)

**Response:**

```json
{
  "runs": [
    {
      "run_id": "20260113_200000",
      "timestamp": "20260113_200000",
      "total_cost": 2.50,
      "total_iterations": 10,
      "success_count": 9,
      "failure_count": 1,
      "elapsed_time_s": 3600
    },
    {
      "run_id": "20260112_150000",
      "timestamp": "20260112_150000",
      "total_cost": 3.20,
      "total_iterations": 12,
      "success_count": 11,
      "failure_count": 1,
      "elapsed_time_s": 4200
    }
  ],
  "total": 50,
  "limit": 20,
  "offset": 0
}
```

**Status Codes:**

- `200 OK`: Success
- `401 Unauthorized`: Missing or invalid token

---

### Get All Runs

**GET** `/api/runs`

Get list of all available runs.

**Authentication**: Required

**Response:**

```json
[
  {
    "run_id": "20260113_200000",
    "timestamp": "20260113_200000",
    "total_cost": 2.50,
    "total_iterations": 10,
    "success_count": 9,
    "failure_count": 1,
    "elapsed_time_s": 3600
  }
]
```

**Status Codes:**

- `200 OK`: Success
- `401 Unauthorized`: Missing or invalid token

---

### Get Run Details

**GET** `/api/runs/<run_id>`

Get detailed information about a specific run.

**Authentication**: Required

**Path Parameters:**

- `run_id`: Run ID (timestamp directory name)

**Response:**

```json
{
  "run_id": "20260113_200000",
  "timestamp": "20260113_200000",
  "summary": {
    "elapsed_time_s": 3600,
    "total_cost": 2.50,
    "total_iterations": 10,
    "success_count": 9,
    "failure_count": 1
  },
  "metrics": {
    "iterations": [ ... ],
    "cache": { ... },
    "parallel": { ... }
  }
}
```

**Status Codes:**

- `200 OK`: Success
- `401 Unauthorized`: Missing or invalid token
- `404 Not Found`: Run not found

---

## Server-Sent Events (SSE)

### Event Stream

**GET** `/api/stream`

Real-time event stream using Server-Sent Events (SSE).

**Authentication**: Required

**Headers:**

```
Authorization: Bearer <token>
Accept: text/event-stream
Cache-Control: no-cache
```

**Event Format:**

```
data: {"type": "status_update", "data": {...}, "timestamp": "2026-01-13T20:00:00Z"}

```

**Event Types:**

1. **connected**: Initial connection event
   ```json
   {
     "type": "connected",
     "timestamp": "2026-01-13T20:00:00Z"
   }
   ```

2. **status_update**: Execution status update
   ```json
   {
     "type": "status_update",
     "data": {
       "is_running": true,
       "current_story": {...},
       "progress_pct": 60.0,
       ...
     },
     "timestamp": "2026-01-13T20:00:00Z"
   }
   ```

3. **keepalive**: Keepalive ping (sent every 30 seconds)
   ```
   : keepalive

   ```

**JavaScript Example:**

```javascript
const token = 'your-auth-token';
const eventSource = new EventSource(
  `http://localhost:8080/api/stream`,
  {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  }
);

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Event:', data.type, data);

  if (data.type === 'status_update') {
    // Update UI with current status
    updateProgressBar(data.data.progress_pct);
  }
};

eventSource.onerror = (error) => {
  console.error('SSE error:', error);
  eventSource.close();
};
```

**Note**: Not all browsers support custom headers with EventSource. For authentication, you may need to pass the token as a query parameter or use a different approach (e.g., polyfill library).

---

## Data Models

### Story Status

```typescript
interface Story {
  id: string;                    // Story ID (e.g., "US-207")
  title: string;                 // Story title
  description: string;           // Story description
  priority: number;              // Priority (lower = higher priority)
  status: "completed" | "pending"; // Completion status
  notes: string;                 // Implementation notes
  estimatedComplexity: "simple" | "medium" | "complex";
  dependencies: string[];        // Array of story IDs this depends on
}
```

### Execution Status

```typescript
interface ExecutionStatus {
  is_running: boolean;           // Whether execution is active
  run_id: string;                // Current run ID
  current_story: {               // Current story being executed
    id: string;
    status: string;
    elapsed_ms: number;
  } | null;
  progress_pct: number;          // Overall progress (0-100)
  completed_stories: number;     // Number of completed stories
  total_stories: number;         // Total number of stories
  elapsed_time: number;          // Elapsed time in seconds
  estimated_remaining: number | null; // Estimated remaining time in seconds
  cost_so_far: number;           // Total cost in USD
  last_update: string;           // ISO timestamp of last update
}
```

### Metrics

```typescript
interface Metrics {
  elapsed_time_s: number;        // Total elapsed time in seconds
  total_cost: number;            // Total cost in USD
  total_iterations: number;      // Total number of iterations
  success_count: number;         // Number of successful iterations
  failure_count: number;         // Number of failed iterations
  last_update: string;           // ISO timestamp of last update
  iterations: Iteration[];       // Array of iteration details
}

interface Iteration {
  story_id: string;
  status: "success" | "failure";
  elapsed_ms: number;
  tokens_in: number;
  tokens_out: number;
  cost: number;
  agents_used: string[];
}
```

---

## Error Handling

### Error Response Format

All errors return a JSON object with an `error` field:

```json
{
  "error": "Error message describing what went wrong"
}
```

### Common Status Codes

- `200 OK`: Request successful
- `401 Unauthorized`: Missing or invalid `Authorization` header
- `403 Forbidden`: Valid header but invalid token
- `404 Not Found`: Resource not found (e.g., run ID doesn't exist)
- `500 Internal Server Error`: Server error (check dashboard logs)

### Authentication Errors

**Missing Authorization Header:**

```json
{
  "error": "Missing or invalid Authorization header"
}
```

**Invalid Token:**

```json
{
  "error": "Invalid authentication token"
}
```

---

## Examples

### Full Workflow Example

```bash
# 1. Start the dashboard
./claude-loop.sh dashboard start --port 8080

# 2. Get the auth token
TOKEN=$(cat .claude-loop/dashboard/auth_token.txt)
echo "Token: $TOKEN"

# 3. Check health (no auth required)
curl http://localhost:8080/api/health

# 4. Get current status
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8080/api/status

# 5. Get all stories
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8080/api/stories

# 6. Get execution logs
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8080/api/logs?limit=10"

# 7. Get metrics
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8080/api/metrics

# 8. Get historical runs
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8080/api/history?limit=5"

# 9. Get details of a specific run
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8080/api/runs/20260113_200000
```

### Python Example

```python
import requests
from pathlib import Path

# Load token
token_file = Path(".claude-loop/dashboard/auth_token.txt")
token = token_file.read_text().strip()

# Base URL
base_url = "http://localhost:8080"

# Headers
headers = {
    "Authorization": f"Bearer {token}"
}

# Get current status
response = requests.get(f"{base_url}/api/status", headers=headers)
status = response.json()
print(f"Progress: {status['progress_pct']}%")
print(f"Completed: {status['completed_stories']}/{status['total_stories']}")

# Get all stories
response = requests.get(f"{base_url}/api/stories", headers=headers)
stories = response.json()
for story in stories['stories']:
    print(f"{story['id']}: {story['title']} - {story['status']}")
```

### JavaScript/Node.js Example

```javascript
const fetch = require('node-fetch');
const fs = require('fs');

// Load token
const token = fs.readFileSync('.claude-loop/dashboard/auth_token.txt', 'utf-8').trim();

// Base URL
const baseUrl = 'http://localhost:8080';

// Headers
const headers = {
  'Authorization': `Bearer ${token}`
};

// Get current status
async function getStatus() {
  const response = await fetch(`${baseUrl}/api/status`, { headers });
  const status = await response.json();
  console.log(`Progress: ${status.progress_pct}%`);
  console.log(`Completed: ${status.completed_stories}/${status.total_stories}`);
}

getStatus();
```

---

## Integration with Frontend

### Building a Dashboard UI

The backend API is designed to be consumed by a web frontend. See `US-208` for the frontend implementation.

**Key Integration Points:**

1. **Initial Load**: Fetch `/api/status`, `/api/stories`, `/api/metrics` on page load
2. **Real-Time Updates**: Connect to `/api/stream` for live updates
3. **Logs Viewer**: Fetch `/api/logs` with pagination
4. **History Browser**: Fetch `/api/history` and `/api/runs/<run_id>` for past runs

### CORS Support

The server has CORS enabled by default for local development. All origins are allowed.

### Production Considerations

- **Security**: Change the default token before deploying to production
- **HTTPS**: Use a reverse proxy (nginx, Apache) with HTTPS in production
- **Rate Limiting**: Consider adding rate limiting for public deployments
- **Logging**: Monitor `.claude-loop/dashboard/dashboard.log` for errors

---

## Troubleshooting

### Server Won't Start

**Error**: `Flask is not installed`

**Solution**: Install Flask and flask-cors:

```bash
pip3 install flask flask-cors
```

### Authentication Fails

**Error**: `Invalid authentication token`

**Solution**: Regenerate the token:

```bash
./claude-loop.sh dashboard generate-token
```

### No Data in Responses

**Issue**: API returns empty arrays or "No metrics available"

**Cause**: No runs have been executed yet, or `.claude-loop/runs/` is empty

**Solution**: Run a PRD execution first:

```bash
./claude-loop.sh --prd prd.json
```

### SSE Connection Drops

**Issue**: EventSource connection closes after 30 seconds

**Cause**: Proxy or load balancer may be timing out idle connections

**Solution**: The server sends keepalive pings every 30 seconds. Adjust proxy timeout settings if needed.

---

## Development

### Running Tests

```bash
# Install test dependencies
pip3 install pytest pytest-flask

# Run tests
pytest tests/dashboard/
```

### Adding New Endpoints

1. Add endpoint handler to `lib/dashboard/server.py`
2. Add data retrieval logic to `lib/dashboard/api.py`
3. Update this documentation
4. Add tests

### Debugging

Enable debug mode for verbose logging:

```bash
python3 lib/dashboard/server.py --debug --port 8080
```

---

## License

Part of claude-loop project. See main repository for license information.
