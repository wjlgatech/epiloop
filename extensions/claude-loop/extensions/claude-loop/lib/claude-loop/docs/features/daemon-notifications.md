# Daemon Mode Notifications

This document describes the notification system for claude-loop daemon mode, which enables email, Slack, and webhook notifications when tasks complete.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Usage](#usage)
- [Notification Channels](#notification-channels)
- [Templates](#templates)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)
- [Examples](#examples)

## Overview

The notification system allows you to receive alerts when daemon tasks complete, fail, or require manual approval. This enables fire-and-forget workflows where you can submit tasks and be notified when they're done.

### Architecture

```
┌─────────────────┐
│  Daemon Task    │
│   Completes     │
└────────┬────────┘
         │
         v
┌─────────────────┐      ┌──────────────┐
│  notifications  │─────→│   Templates  │
│      .sh        │      │  (success/   │
└────────┬────────┘      │  failure/    │
         │               │  checkpoint) │
         │               └──────────────┘
         v
┌─────────────────┐
│   Retry Logic   │
│  (exponential   │
│   backoff)      │
└────────┬────────┘
         │
         ├──→ Email (sendmail/SMTP)
         ├──→ Slack Webhook
         └──→ Generic Webhook

```

## Features

### Multi-Channel Support

- **Email Notifications**: Via sendmail or SMTP
- **Slack Notifications**: Via webhook integration
- **Generic Webhooks**: POST JSON to any endpoint

### Reliability

- **Retry Logic**: Up to 3 retries with exponential backoff
- **Error Handling**: Graceful degradation if channels fail
- **Logging**: All notification attempts logged

### Flexibility

- **Multiple Channels**: Send to one or all channels per task
- **Customizable Templates**: Modify notification content
- **Configurable Retries**: Adjust retry count and delay
- **Task Metadata**: Include project, stories, time, cost

## Quick Start

### 1. Initialize Notifications

```bash
./lib/notifications.sh init
```

This creates:
- `.claude-loop/daemon/notifications.json` - Configuration file
- `templates/notifications/` - Template directory

### 2. Configure Channels

Edit `.claude-loop/daemon/notifications.json`:

```json
{
  "email": {
    "enabled": true,
    "method": "sendmail",
    "from": "claude-loop@yourcompany.com",
    "to": ["you@example.com"]
  },
  "slack": {
    "enabled": true,
    "webhook_url": "https://hooks.slack.com/services/YOUR/WEBHOOK/URL",
    "channel": "#dev-notifications"
  },
  "webhook": {
    "enabled": false
  }
}
```

### 3. Submit Task with Notifications

```bash
./lib/daemon.sh submit prd.json --notify email,slack
```

### 4. Receive Notifications

When the task completes, you'll receive notifications via your configured channels!

## Configuration

### Configuration File

Location: `.claude-loop/daemon/notifications.json`

### Email Configuration

#### Sendmail Method (Default)

```json
{
  "email": {
    "enabled": true,
    "method": "sendmail",
    "from": "claude-loop@localhost",
    "to": ["recipient@example.com", "team@example.com"]
  }
}
```

**Requirements**:
- Sendmail must be installed and configured on the system

#### SMTP Method

```json
{
  "email": {
    "enabled": true,
    "method": "smtp",
    "from": "claude-loop@yourcompany.com",
    "to": ["recipient@example.com"],
    "smtp": {
      "host": "smtp.gmail.com",
      "port": 587,
      "username": "your-email@gmail.com",
      "password": "your-app-password",
      "tls": true
    }
  }
}
```

**Security Note**: Store SMTP credentials securely. Consider using app-specific passwords.

### Slack Configuration

```json
{
  "slack": {
    "enabled": true,
    "webhook_url": "https://hooks.slack.com/services/YOUR/WEBHOOK/URL",
    "channel": "#claude-loop",
    "username": "claude-loop",
    "icon_emoji": ":robot_face:"
  }
}
```

**Setup Instructions**:
1. Go to https://api.slack.com/apps
2. Create a new app or select existing app
3. Enable "Incoming Webhooks"
4. Add webhook to workspace
5. Copy webhook URL to configuration

### Webhook Configuration

```json
{
  "webhook": {
    "enabled": true,
    "url": "https://your-api.com/webhook",
    "method": "POST",
    "headers": {},
    "auth": {
      "type": "bearer",
      "token": "your-api-token"
    }
  }
}
```

**Auth Types**:
- `none`: No authentication
- `bearer`: Bearer token in Authorization header

### Global Defaults

```json
{
  "defaults": {
    "max_retries": 3,
    "retry_delay": 5,
    "timeout": 30
  }
}
```

- `max_retries`: Number of retry attempts (1-10)
- `retry_delay`: Initial delay in seconds (exponential backoff)
- `timeout`: Request timeout in seconds

## Usage

### Submit Task with Notifications

```bash
# Single channel
./lib/daemon.sh submit prd.json --notify email

# Multiple channels
./lib/daemon.sh submit prd.json --notify email,slack,webhook

# With priority
./lib/daemon.sh submit prd.json --priority high --notify slack
```

### Test Notifications

```bash
# Test email
./lib/notifications.sh test-email you@example.com

# Test Slack
./lib/notifications.sh test-slack

# Test webhook
./lib/notifications.sh test-webhook
```

### Manual Notification

```bash
# Send notification manually
./lib/notifications.sh notify "TASK-001" "completed" \
  '{"project":"test","stories_completed":5,"time_taken":"10m","cost":"$0.50"}' \
  "email,slack"
```

## Notification Channels

### Email

**Format**: Plain text email with task summary

**Subject**: `claude-loop: Task {task_id} {status}`

**Body**: Uses template from `templates/notifications/{status}.txt`

**Recipients**: All addresses in `email.to` array receive individual emails

### Slack

**Format**: Slack message with attachment (colored based on status)

**Colors**:
- `good` (green): Success
- `danger` (red): Failure
- `warning` (orange): Checkpoint required

**Message Structure**:
```
Title: claude-loop: Task {task_id} {status}
Text: {template content}
Footer: claude-loop
Timestamp: {unix timestamp}
```

### Webhook

**Format**: JSON POST request

**Payload**:
```json
{
  "task_id": "abc123",
  "status": "completed",
  "project": "my-project",
  "stories_completed": 5,
  "time_taken": "15m 30s",
  "cost": "$1.25",
  "timestamp": "2026-01-13T10:30:00Z"
}
```

**Headers**:
- `Content-Type: application/json`
- `Authorization: Bearer {token}` (if configured)

## Templates

Templates are located in `templates/notifications/` and use variable substitution.

### Available Templates

1. **success.txt**: Task completed successfully
2. **failure.txt**: Task failed
3. **checkpoint.txt**: Manual approval required

### Template Variables

Available variables:
- `{{TASK_ID}}`: Task identifier
- `{{STATUS}}`: Task status (completed, failed, checkpoint)
- `{{PROJECT}}`: Project name from PRD
- `{{STORIES_COMPLETED}}`: Number of completed stories
- `{{TIME_TAKEN}}`: Elapsed time (formatted)
- `{{COST}}`: Estimated cost

### Example Template

```
✅ Task Completed Successfully

Task ID: {{TASK_ID}}
Status: {{STATUS}}
Project: {{PROJECT}}

Results:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✓ Stories Completed: {{STORIES_COMPLETED}}
✓ Time Taken: {{TIME_TAKEN}}
✓ Cost: {{COST}}

All user stories have been implemented successfully and tests are passing.

--
claude-loop autonomous feature implementation
```

### Custom Templates

Create new templates in `templates/notifications/`:

```bash
# Create custom template
cat > templates/notifications/custom.txt << 'EOF'
Custom notification for {{PROJECT}}
Task: {{TASK_ID}}
Status: {{STATUS}}
EOF

# Use in notification
./lib/notifications.sh notify "TASK-001" "custom" '{"project":"test"}' "email"
```

## Testing

### Run Test Suite

```bash
./tests/notifications/test_notifications.sh
```

**Test Coverage**:
- Initialization
- Configuration structure
- Template rendering
- Notification logging
- Retry logic
- Channel status checking
- CLI interface
- Daemon integration

### Manual Testing

```bash
# 1. Initialize
./lib/notifications.sh init

# 2. Test each channel
./lib/notifications.sh test-email your-email@example.com
./lib/notifications.sh test-slack
./lib/notifications.sh test-webhook

# 3. Check logs
tail -f .claude-loop/daemon/notifications.log
```

## Troubleshooting

### Email Not Sending

**Problem**: Email notifications not received

**Solutions**:

1. **Check sendmail**:
   ```bash
   which sendmail
   echo "Test" | sendmail -v you@example.com
   ```

2. **Try SMTP method**:
   Switch from sendmail to SMTP in configuration

3. **Check spam folder**: Emails might be filtered

4. **Verify configuration**:
   ```bash
   cat .claude-loop/daemon/notifications.json | grep -A 10 email
   ```

5. **Check logs**:
   ```bash
   grep -i email .claude-loop/daemon/notifications.log
   ```

### Slack Webhook Failing

**Problem**: Slack notifications not appearing

**Solutions**:

1. **Verify webhook URL**:
   ```bash
   curl -X POST \
     -H 'Content-Type: application/json' \
     -d '{"text":"Test"}' \
     YOUR_WEBHOOK_URL
   ```

2. **Check channel permissions**: Ensure webhook has access to channel

3. **Regenerate webhook**: Old webhooks may expire

4. **Check rate limits**: Slack has rate limits for webhooks

### Generic Webhook Errors

**Problem**: Webhook requests failing

**Solutions**:

1. **Test endpoint manually**:
   ```bash
   curl -X POST \
     -H 'Content-Type: application/json' \
     -H 'Authorization: Bearer YOUR_TOKEN' \
     -d '{"test":true}' \
     YOUR_ENDPOINT
   ```

2. **Check auth configuration**: Verify token is correct

3. **Check SSL/TLS**: Endpoint may require specific certificates

4. **Review timeout**: Increase timeout if endpoint is slow

### Retries Not Working

**Problem**: Failed notifications not retrying

**Solutions**:

1. **Check retry configuration**:
   ```bash
   cat .claude-loop/daemon/notifications.json | grep -A 5 defaults
   ```

2. **Increase max_retries**: Set higher value (e.g., 5)

3. **Increase retry_delay**: Allow more time between retries

4. **Check logs for errors**:
   ```bash
   grep -i retry .claude-loop/daemon/notifications.log
   ```

### Logs

Check these log files for debugging:

```bash
# Notification-specific logs
tail -f .claude-loop/daemon/notifications.log

# Daemon logs (includes notification calls)
tail -f .claude-loop/daemon/daemon.log

# Test stderr output
./lib/notifications.sh test-slack 2>&1 | tee test.log
```

## Examples

### Example 1: Email Only

```bash
# Configure email
cat > .claude-loop/daemon/notifications.json << 'EOF'
{
  "email": {
    "enabled": true,
    "method": "sendmail",
    "from": "claude-loop@company.com",
    "to": ["dev-team@company.com"]
  },
  "slack": {"enabled": false},
  "webhook": {"enabled": false},
  "defaults": {"max_retries": 3, "retry_delay": 5, "timeout": 30}
}
EOF

# Submit task
./lib/daemon.sh submit prd.json --notify email
```

### Example 2: Slack with Custom Channel

```bash
# Configure Slack
cat > .claude-loop/daemon/notifications.json << 'EOF'
{
  "email": {"enabled": false},
  "slack": {
    "enabled": true,
    "webhook_url": "https://hooks.slack.com/services/YOUR/WEBHOOK",
    "channel": "#production-deploys",
    "username": "DeployBot",
    "icon_emoji": ":rocket:"
  },
  "webhook": {"enabled": false},
  "defaults": {"max_retries": 3, "retry_delay": 5, "timeout": 30}
}
EOF

# Submit task
./lib/daemon.sh submit production-prd.json --priority high --notify slack
```

### Example 3: All Channels

```bash
# Configure all channels
cat > .claude-loop/daemon/notifications.json << 'EOF'
{
  "email": {
    "enabled": true,
    "method": "smtp",
    "from": "notifications@company.com",
    "to": ["dev-team@company.com", "manager@company.com"],
    "smtp": {
      "host": "smtp.gmail.com",
      "port": 587,
      "username": "notifications@company.com",
      "password": "app-specific-password",
      "tls": true
    }
  },
  "slack": {
    "enabled": true,
    "webhook_url": "https://hooks.slack.com/services/YOUR/WEBHOOK",
    "channel": "#deployments"
  },
  "webhook": {
    "enabled": true,
    "url": "https://api.company.com/webhooks/claude-loop",
    "method": "POST",
    "auth": {
      "type": "bearer",
      "token": "secret-token"
    }
  },
  "defaults": {"max_retries": 5, "retry_delay": 3, "timeout": 60}
}
EOF

# Submit task with all notifications
./lib/daemon.sh submit prd.json --notify email,slack,webhook
```

### Example 4: Custom Template

```bash
# Create custom template
cat > templates/notifications/deployment.txt << 'EOF'
🚀 Deployment Complete

Environment: Production
Task ID: {{TASK_ID}}
Project: {{PROJECT}}

Deployment Summary:
────────────────────
✓ Features: {{STORIES_COMPLETED}}
✓ Duration: {{TIME_TAKEN}}
✓ Cost: {{COST}}

Status: All checks passed ✅

Next Steps:
1. Monitor application logs
2. Run smoke tests
3. Notify stakeholders

--
Automated by claude-loop
EOF

# Use custom template in notification
./lib/notifications.sh notify "DEPLOY-001" "deployment" \
  '{"project":"webapp","stories_completed":3,"time_taken":"8m","cost":"$0.75"}' \
  "email,slack"
```

### Example 5: Conditional Notifications

```bash
# Only notify on failure (scripted example)
submit_with_failure_notifications() {
    local prd_path="$1"
    local task_id

    # Submit without notifications
    task_id=$(./lib/daemon.sh submit "${prd_path}" | grep -oE 'ID: [a-z0-9]+' | cut -d: -f2 | tr -d ' ')

    # Wait for task completion
    while true; do
        status=$(./lib/daemon.sh queue | grep "${task_id}" | awk '{print $3}')
        if [[ "${status}" == "completed" ]]; then
            echo "Task succeeded, no notification sent"
            break
        elif [[ "${status}" == "failed" ]]; then
            # Send notification on failure
            ./lib/notifications.sh notify "${task_id}" "failure" \
                '{"project":"test","stories_completed":0,"time_taken":"5m","cost":"$0.25"}' \
                "email,slack"
            echo "Task failed, notification sent"
            break
        fi
        sleep 10
    done
}
```

## Integration with Daemon

Notifications are automatically integrated with daemon mode. When a task completes, the daemon:

1. Checks if notification channels were specified
2. Extracts task metadata (project, stories, time, cost)
3. Selects appropriate template (success/failure/checkpoint)
4. Renders template with task variables
5. Sends notification to each enabled channel
6. Retries on failure with exponential backoff
7. Logs all attempts

### Daemon Integration Points

The daemon calls notifications at these points:

```bash
# In lib/daemon.sh, execute_task function:

# Task completes successfully
update_task_status "${task_id}" "completed" "success"
# → Sends "success" notification

# Task fails
update_task_status "${task_id}" "failed" "execution_error"
# → Sends "failure" notification

# Manual checkpoint required (future)
update_task_status "${task_id}" "checkpoint_required"
# → Sends "checkpoint" notification
```

## Best Practices

### Security

1. **Don't commit credentials**: Add `.claude-loop/daemon/notifications.json` to `.gitignore`
2. **Use app passwords**: For Gmail SMTP, use app-specific passwords
3. **Rotate tokens**: Regularly rotate webhook tokens and API keys
4. **Limit permissions**: Give webhooks minimal required permissions

### Reliability

1. **Test first**: Always test notifications before production use
2. **Monitor logs**: Regularly check notification logs for errors
3. **Set reasonable retries**: 3-5 retries is usually sufficient
4. **Use multiple channels**: Configure backup channels for critical tasks

### Performance

1. **Batch recipients**: Use `to` array for multiple email recipients
2. **Adjust timeouts**: Increase timeout for slow endpoints
3. **Limit retry delay**: Balance reliability with speed

### Maintenance

1. **Review templates**: Update templates with relevant information
2. **Clean logs**: Rotate or archive old notification logs
3. **Update webhooks**: Keep webhook URLs current
4. **Test periodically**: Run test suite regularly

## Advanced Configuration

### Environment Variables

Override configuration via environment variables:

```bash
# Retry configuration
export NOTIFICATION_MAX_RETRIES=5
export NOTIFICATION_RETRY_DELAY=10
export NOTIFICATION_TIMEOUT=60

# Channel overrides
export NOTIFICATION_SLACK_ENABLED=true
export NOTIFICATION_EMAIL_ENABLED=false
```

### Dynamic Channel Selection

Select channels based on task priority:

```bash
# High priority: All channels
./lib/daemon.sh submit critical-prd.json --priority high --notify email,slack,webhook

# Normal priority: Slack only
./lib/daemon.sh submit standard-prd.json --notify slack

# Low priority: No notifications
./lib/daemon.sh submit background-prd.json
```

### Custom Notification Logic

Extend notification system with custom handlers:

```bash
# In lib/notifications.sh, add custom handler:
send_custom_notification() {
    local message="$1"
    # Your custom logic here
    curl -X POST https://custom-api.com/notify \
        -d "${message}"
}

# Call from notify_task_complete function
```

## API Reference

### CLI Commands

```bash
./lib/notifications.sh init                  # Initialize system
./lib/notifications.sh test-email <to>       # Test email
./lib/notifications.sh test-slack            # Test Slack
./lib/notifications.sh test-webhook          # Test webhook
./lib/notifications.sh notify <id> <status>  # Send notification
```

### Functions

When sourcing `lib/notifications.sh`:

```bash
source lib/notifications.sh

init_notifications                           # Initialize directories and config
log_notification "INFO" "message"            # Log to notifications.log
get_config "email.enabled"                   # Get config value
is_channel_enabled "slack"                   # Check if channel enabled
send_email "to" "subject" "body"             # Send email
send_slack "message" "title" "color"         # Send Slack message
send_webhook "json_payload"                  # Send webhook
retry_with_backoff 3 5 command               # Retry with exponential backoff
load_template "success"                      # Load template file
render_template "text" "VAR" "value"         # Render template variables
notify_task_complete "id" "status" "data"    # Send all notifications
```

## FAQ

**Q: Can I use multiple Slack channels?**
A: Currently one channel per configuration, but you can send to multiple via webhook channel pointing to a relay service.

**Q: How do I disable notifications for specific tasks?**
A: Simply omit the `--notify` flag when submitting the task.

**Q: Can notifications include task logs?**
A: Not directly, but you can customize templates to include log paths or add links to log viewer.

**Q: What happens if all notification channels fail?**
A: The task continues and completes. Notification failures are logged but don't affect task execution.

**Q: Can I get notifications during task execution, not just at completion?**
A: Currently no, but you can monitor `.claude-loop/daemon/daemon.log` for progress updates.

**Q: How do I add a new notification channel (e.g., Discord, PagerDuty)?**
A: Extend `lib/notifications.sh` with a new `send_discord()` function and add configuration section.

## Contributing

To add new notification channels:

1. Add configuration section to default config
2. Implement `send_<channel>()` function
3. Add channel to `notify_task_complete()` logic
4. Add test command to CLI
5. Update documentation
6. Submit PR with tests

## See Also

- [Daemon Mode Core Infrastructure](./daemon-mode.md)
- [Quick Task Mode](./quick-task-mode.md)
- [Visual Progress Dashboard](./dashboard-ui.md)
