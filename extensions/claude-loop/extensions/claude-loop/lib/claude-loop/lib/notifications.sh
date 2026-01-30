#!/usr/bin/env bash
#
# notifications.sh - Notification system for claude-loop daemon
#
# Features:
# - Email notifications via sendmail/SMTP
# - Slack webhook notifications
# - Generic webhook notifications
# - Notification templates
# - Retry logic with exponential backoff
# - Multiple notification channels per task
# - Configuration management
#

set -euo pipefail

# Configuration
NOTIFICATIONS_DIR="${CLAUDE_LOOP_DIR:-.claude-loop}/daemon"
NOTIFICATIONS_CONFIG="${NOTIFICATIONS_DIR}/notifications.json"
NOTIFICATIONS_LOG="${NOTIFICATIONS_DIR}/notifications.log"
TEMPLATES_DIR="templates/notifications"

# Default configuration
DEFAULT_MAX_RETRIES=3
DEFAULT_RETRY_DELAY=5
DEFAULT_TIMEOUT=30

# Initialize notifications directory and config
init_notifications() {
    mkdir -p "${NOTIFICATIONS_DIR}"
    mkdir -p "${TEMPLATES_DIR}"

    # Create default config if it doesn't exist
    if [[ ! -f "${NOTIFICATIONS_CONFIG}" ]]; then
        cat > "${NOTIFICATIONS_CONFIG}" << 'EOF'
{
  "email": {
    "enabled": false,
    "method": "sendmail",
    "from": "claude-loop@localhost",
    "to": [],
    "smtp": {
      "host": "localhost",
      "port": 587,
      "username": "",
      "password": "",
      "tls": true
    }
  },
  "slack": {
    "enabled": false,
    "webhook_url": "",
    "channel": "#claude-loop",
    "username": "claude-loop",
    "icon_emoji": ":robot_face:"
  },
  "webhook": {
    "enabled": false,
    "url": "",
    "method": "POST",
    "headers": {},
    "auth": {
      "type": "none",
      "token": ""
    }
  },
  "defaults": {
    "max_retries": 3,
    "retry_delay": 5,
    "timeout": 30
  }
}
EOF
    fi
}

# Logging function
log_notification() {
    local level="$1"
    shift
    local message="$*"
    local timestamp
    timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    echo "[${timestamp}] [${level}] ${message}" >> "${NOTIFICATIONS_LOG}"
}

# Get configuration value
get_config() {
    local key="$1"
    local default="${2:-}"

    if [[ -f "${NOTIFICATIONS_CONFIG}" ]]; then
        python3 -c "
import json
import sys
try:
    with open('${NOTIFICATIONS_CONFIG}', 'r') as f:
        config = json.load(f)
    keys = '${key}'.split('.')
    value = config
    for k in keys:
        value = value.get(k, {})
    if value:
        print(value)
    else:
        print('${default}')
except:
    print('${default}')
" || echo "${default}"
    else
        echo "${default}"
    fi
}

# Check if notification channel is enabled
is_channel_enabled() {
    local channel="$1"
    local enabled
    enabled=$(get_config "${channel}.enabled" "false")
    [[ "${enabled}" == "True" ]] || [[ "${enabled}" == "true" ]]
}

# Send email notification via sendmail
send_email_sendmail() {
    local to="$1"
    local subject="$2"
    local body="$3"
    local from
    from=$(get_config "email.from" "claude-loop@localhost")

    local email_content
    email_content=$(cat << EOF
To: ${to}
From: ${from}
Subject: ${subject}
Content-Type: text/plain; charset=UTF-8

${body}
EOF
)

    echo "${email_content}" | sendmail -t
}

# Send email notification via SMTP
send_email_smtp() {
    local to="$1"
    local subject="$2"
    local body="$3"

    python3 << 'PYEOF'
import smtplib
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import sys

# Read config
with open('${NOTIFICATIONS_CONFIG}', 'r') as f:
    config = json.load(f)

email_config = config['email']
smtp_config = email_config['smtp']

# Create message
msg = MIMEMultipart()
msg['From'] = email_config['from']
msg['To'] = sys.argv[1]
msg['Subject'] = sys.argv[2]
msg.attach(MIMEText(sys.argv[3], 'plain'))

# Send email
try:
    if smtp_config.get('tls', True):
        server = smtplib.SMTP(smtp_config['host'], smtp_config['port'], timeout=30)
        server.starttls()
    else:
        server = smtplib.SMTP(smtp_config['host'], smtp_config['port'], timeout=30)

    if smtp_config.get('username') and smtp_config.get('password'):
        server.login(smtp_config['username'], smtp_config['password'])

    server.send_message(msg)
    server.quit()
    print("Email sent successfully")
except Exception as e:
    print(f"Error sending email: {e}", file=sys.stderr)
    sys.exit(1)
PYEOF
}

# Send email notification
send_email() {
    local to="$1"
    local subject="$2"
    local body="$3"

    local method
    method=$(get_config "email.method" "sendmail")

    log_notification "INFO" "Sending email to ${to} via ${method}"

    if [[ "${method}" == "smtp" ]]; then
        send_email_smtp "${to}" "${subject}" "${body}"
    else
        send_email_sendmail "${to}" "${subject}" "${body}"
    fi
}

# Send Slack notification
send_slack() {
    local message="$1"
    local title="${2:-}"
    local color="${3:-good}"

    local webhook_url
    webhook_url=$(get_config "slack.webhook_url")

    if [[ -z "${webhook_url}" ]]; then
        log_notification "ERROR" "Slack webhook URL not configured"
        return 1
    fi

    local channel username icon_emoji
    channel=$(get_config "slack.channel" "#claude-loop")
    username=$(get_config "slack.username" "claude-loop")
    icon_emoji=$(get_config "slack.icon_emoji" ":robot_face:")

    log_notification "INFO" "Sending Slack notification to ${channel}"

    local payload
    if [[ -n "${title}" ]]; then
        payload=$(cat << EOF
{
  "channel": "${channel}",
  "username": "${username}",
  "icon_emoji": "${icon_emoji}",
  "attachments": [
    {
      "title": "${title}",
      "text": "${message}",
      "color": "${color}",
      "footer": "claude-loop",
      "ts": $(date +%s)
    }
  ]
}
EOF
)
    else
        payload=$(cat << EOF
{
  "channel": "${channel}",
  "username": "${username}",
  "icon_emoji": "${icon_emoji}",
  "text": "${message}"
}
EOF
)
    fi

    local timeout
    timeout=$(get_config "defaults.timeout" "${DEFAULT_TIMEOUT}")

    curl -X POST \
        -H "Content-Type: application/json" \
        -d "${payload}" \
        --max-time "${timeout}" \
        --silent \
        --show-error \
        "${webhook_url}"
}

# Send generic webhook notification
send_webhook() {
    local payload="$1"

    local webhook_url method
    webhook_url=$(get_config "webhook.url")
    method=$(get_config "webhook.method" "POST")

    if [[ -z "${webhook_url}" ]]; then
        log_notification "ERROR" "Webhook URL not configured"
        return 1
    fi

    log_notification "INFO" "Sending webhook notification to ${webhook_url}"

    local timeout
    timeout=$(get_config "defaults.timeout" "${DEFAULT_TIMEOUT}")

    # SECURITY: Build curl command using array instead of eval to prevent command injection
    declare -a curl_args
    curl_args=(-X "${method}")
    curl_args+=(-H "Content-Type: application/json")

    # Add auth if configured
    local auth_type
    auth_type=$(get_config "webhook.auth.type" "none")
    if [[ "${auth_type}" == "bearer" ]]; then
        local token
        token=$(get_config "webhook.auth.token")
        if [[ -n "${token}" ]]; then
            curl_args+=(-H "Authorization: Bearer ${token}")
        fi
    fi

    curl_args+=(-d "${payload}")
    curl_args+=(--max-time "${timeout}")
    curl_args+=(--silent --show-error)
    curl_args+=("${webhook_url}")

    # Safe execution without eval
    if ! curl "${curl_args[@]}" 2>&1; then
        log_notification "ERROR" "curl failed with exit code $?"
        return 1
    fi
}

# Retry wrapper with exponential backoff
retry_with_backoff() {
    local max_retries="${1}"
    local retry_delay="${2}"
    shift 2
    local cmd=("$@")

    local attempt=1
    local delay="${retry_delay}"

    while [[ ${attempt} -le ${max_retries} ]]; do
        log_notification "INFO" "Attempt ${attempt}/${max_retries}: ${cmd[*]}"

        if "${cmd[@]}"; then
            log_notification "INFO" "Success on attempt ${attempt}"
            return 0
        fi

        if [[ ${attempt} -lt ${max_retries} ]]; then
            log_notification "WARN" "Attempt ${attempt} failed, retrying in ${delay}s"
            sleep "${delay}"
            delay=$((delay * 2))  # Exponential backoff
        else
            log_notification "ERROR" "All ${max_retries} attempts failed"
        fi

        attempt=$((attempt + 1))
    done

    return 1
}

# Load notification template
load_template() {
    local template_name="$1"
    local template_file="${TEMPLATES_DIR}/${template_name}.txt"

    if [[ -f "${template_file}" ]]; then
        cat "${template_file}"
    else
        log_notification "WARN" "Template ${template_name} not found"
        echo ""
    fi
}

# Render template with variables
render_template() {
    local template="$1"
    shift

    # Replace variables in template
    # Format: {{VARIABLE_NAME}}
    local rendered="${template}"
    while [[ $# -gt 0 ]]; do
        local var_name="$1"
        local var_value="$2"
        rendered="${rendered//\{\{${var_name}\}\}/${var_value}}"
        shift 2
    done

    echo "${rendered}"
}

# Send notification for task completion
notify_task_complete() {
    local task_id="$1"
    local task_status="$2"
    local task_data="$3"
    local channels="${4:-email,slack,webhook}"

    init_notifications

    # Parse task data
    local project stories_completed time_taken cost
    project=$(echo "${task_data}" | python3 -c "import json, sys; data=json.load(sys.stdin); print(data.get('project', 'unknown'))")
    stories_completed=$(echo "${task_data}" | python3 -c "import json, sys; data=json.load(sys.stdin); print(data.get('stories_completed', 0))")
    time_taken=$(echo "${task_data}" | python3 -c "import json, sys; data=json.load(sys.stdin); print(data.get('time_taken', '0s'))")
    cost=$(echo "${task_data}" | python3 -c "import json, sys; data=json.load(sys.stdin); print(data.get('cost', '$0.00'))")

    # Determine template and color based on status
    local template_name color
    if [[ "${task_status}" == "completed" ]]; then
        template_name="success"
        color="good"
    elif [[ "${task_status}" == "failed" ]]; then
        template_name="failure"
        color="danger"
    else
        template_name="checkpoint"
        color="warning"
    fi

    # Load and render template
    local template body
    template=$(load_template "${template_name}")
    body=$(render_template "${template}" \
        "TASK_ID" "${task_id}" \
        "STATUS" "${task_status}" \
        "PROJECT" "${project}" \
        "STORIES_COMPLETED" "${stories_completed}" \
        "TIME_TAKEN" "${time_taken}" \
        "COST" "${cost}")

    # If template is empty, use default message
    if [[ -z "${body}" ]]; then
        body="Task ${task_id} ${task_status}\n\nProject: ${project}\nStories: ${stories_completed}\nTime: ${time_taken}\nCost: ${cost}"
    fi

    local subject="claude-loop: Task ${task_id} ${task_status}"

    # Get retry configuration
    local max_retries retry_delay
    max_retries=$(get_config "defaults.max_retries" "${DEFAULT_MAX_RETRIES}")
    retry_delay=$(get_config "defaults.retry_delay" "${DEFAULT_RETRY_DELAY}")

    # Send to each enabled channel
    IFS=',' read -ra CHANNELS <<< "${channels}"
    for channel in "${CHANNELS[@]}"; do
        channel=$(echo "${channel}" | xargs)  # Trim whitespace

        if [[ "${channel}" == "email" ]] && is_channel_enabled "email"; then
            local recipients
            recipients=$(get_config "email.to" | python3 -c "import json, sys; print(','.join(json.load(sys.stdin)))")

            if [[ -n "${recipients}" ]]; then
                IFS=',' read -ra TO_ADDRS <<< "${recipients}"
                for to_addr in "${TO_ADDRS[@]}"; do
                    retry_with_backoff "${max_retries}" "${retry_delay}" \
                        send_email "${to_addr}" "${subject}" "${body}"
                done
            fi

        elif [[ "${channel}" == "slack" ]] && is_channel_enabled "slack"; then
            retry_with_backoff "${max_retries}" "${retry_delay}" \
                send_slack "${body}" "${subject}" "${color}"

        elif [[ "${channel}" == "webhook" ]] && is_channel_enabled "webhook"; then
            local webhook_payload
            webhook_payload=$(cat << EOF
{
  "task_id": "${task_id}",
  "status": "${task_status}",
  "project": "${project}",
  "stories_completed": ${stories_completed},
  "time_taken": "${time_taken}",
  "cost": "${cost}",
  "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
}
EOF
)
            retry_with_backoff "${max_retries}" "${retry_delay}" \
                send_webhook "${webhook_payload}"
        fi
    done

    log_notification "INFO" "Notifications sent for task ${task_id}"
}

# CLI interface
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    command="${1:-}"
    shift || true

    case "${command}" in
        init)
            init_notifications
            echo "Notifications initialized"
            ;;
        test-email)
            to="${1:-}"
            if [[ -z "${to}" ]]; then
                echo "Usage: $0 test-email <recipient>"
                exit 1
            fi
            send_email "${to}" "Test notification from claude-loop" "This is a test email from claude-loop notifications system."
            echo "Test email sent to ${to}"
            ;;
        test-slack)
            send_slack "This is a test notification from claude-loop" "Test Notification" "good"
            echo "Test Slack notification sent"
            ;;
        test-webhook)
            payload='{"test": true, "message": "Test notification from claude-loop"}'
            send_webhook "${payload}"
            echo "Test webhook notification sent"
            ;;
        notify)
            task_id="${1:-}"
            status="${2:-}"
            data="${3:-{}}"
            channels="${4:-email,slack,webhook}"
            if [[ -z "${task_id}" ]] || [[ -z "${status}" ]]; then
                echo "Usage: $0 notify <task_id> <status> [data_json] [channels]"
                exit 1
            fi
            notify_task_complete "${task_id}" "${status}" "${data}" "${channels}"
            ;;
        *)
            cat << 'USAGE'
Usage: notifications.sh <command> [options]

Commands:
  init                      Initialize notifications system
  test-email <to>           Send test email notification
  test-slack                Send test Slack notification
  test-webhook              Send test webhook notification
  notify <id> <status>      Send notification for task completion
                            [data_json] [channels]

Configuration:
  Edit .claude-loop/daemon/notifications.json to configure channels
USAGE
            ;;
    esac
fi
