#!/usr/bin/env python3
"""
Slack Notification Hook

Sends Slack notifications for key lifecycle events.
Useful for monitoring long-running autonomous sessions.
"""

import os
import json
import requests
from typing import Optional

# Add lib to path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'lib'))

from hooks import HookContext, HookType, register_hook


class SlackNotifier:
    """Send notifications to Slack via webhook."""

    def __init__(self, webhook_url: Optional[str] = None):
        """
        Initialize Slack notifier.

        Args:
            webhook_url: Slack webhook URL (defaults to SLACK_WEBHOOK_URL env var)
        """
        self.webhook_url = webhook_url or os.getenv('SLACK_WEBHOOK_URL')

        if not self.webhook_url:
            raise ValueError("SLACK_WEBHOOK_URL environment variable not set")

    def send_message(self, text: str, blocks: Optional[list] = None):
        """
        Send message to Slack.

        Args:
            text: Plain text message
            blocks: Optional Slack blocks for rich formatting
        """
        payload = {"text": text}

        if blocks:
            payload["blocks"] = blocks

        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=5
            )
            response.raise_for_status()
        except Exception as e:
            # Don't fail the hook, just log
            print(f"Failed to send Slack notification: {e}")


def notify_story_start(context: HookContext) -> HookContext:
    """
    Notify when a story starts.

    Hook: BEFORE_STORY_START
    Priority: 50
    """
    try:
        notifier = SlackNotifier()

        project = "Unknown"
        if context.prd_data:
            project = context.prd_data.get('project', 'Unknown')

        text = f":rocket: Story Started: {context.story_id}"
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"Story Started: {context.story_id}"
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Project:*\n{project}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Session:*\n{context.session_id or 'N/A'}"
                    }
                ]
            }
        ]

        notifier.send_message(text, blocks)

    except Exception as e:
        # Error isolation: don't fail the hook
        print(f"Slack notification hook failed: {e}")

    return context


def notify_story_complete(context: HookContext) -> HookContext:
    """
    Notify when a story completes.

    Hook: AFTER_STORY_COMPLETE
    Priority: 50
    """
    try:
        notifier = SlackNotifier()

        text = f":white_check_mark: Story Completed: {context.story_id}"
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"Story Completed: {context.story_id}"
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Iteration:*\n{context.iteration}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Session:*\n{context.session_id or 'N/A'}"
                    }
                ]
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": ":robot_face: Sent by claude-loop"
                    }
                ]
            }
        ]

        notifier.send_message(text, blocks)

    except Exception as e:
        print(f"Slack notification hook failed: {e}")

    return context


def notify_error(context: HookContext) -> HookContext:
    """
    Notify when an error occurs.

    Hook: ON_ERROR
    Priority: 75 (higher priority for errors)
    """
    try:
        if not context.error:
            return context

        notifier = SlackNotifier()

        error_msg = str(context.error)[:200]  # Truncate long errors

        text = f":warning: Error in Story: {context.story_id}"
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"Error: {context.story_id}"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"```\n{error_msg}\n```"
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Iteration: {context.iteration}"
                    }
                ]
            }
        ]

        notifier.send_message(text, blocks)

    except Exception as e:
        print(f"Slack notification hook failed: {e}")

    return context


def notify_session_end(context: HookContext) -> HookContext:
    """
    Notify when a session ends.

    Hook: ON_SESSION_END
    Priority: 50
    """
    try:
        notifier = SlackNotifier()

        text = f":checkered_flag: Session Ended: {context.session_id}"
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "Session Ended"
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Session ID:*\n{context.session_id or 'N/A'}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Total Iterations:*\n{context.iteration}"
                    }
                ]
            }
        ]

        notifier.send_message(text, blocks)

    except Exception as e:
        print(f"Slack notification hook failed: {e}")

    return context


# Register hooks when module is imported
if __name__ != "__main__":
    # Only register if webhook URL is configured
    if os.getenv('SLACK_WEBHOOK_URL'):
        register_hook(HookType.BEFORE_STORY_START, notify_story_start, priority=50)
        register_hook(HookType.AFTER_STORY_COMPLETE, notify_story_complete, priority=50)
        register_hook(HookType.ON_ERROR, notify_error, priority=75)
        register_hook(HookType.ON_SESSION_END, notify_session_end, priority=50)
        print("Slack notification hooks registered")
    else:
        print("Slack webhook URL not configured, skipping Slack hooks")


# Example usage
if __name__ == "__main__":
    # Test the hooks
    print("Testing Slack notification hooks...")

    # Create test context
    test_context = HookContext(
        story_id="US-TEST",
        prd_data={"project": "test-project"},
        session_id="test-session-123",
        iteration=5
    )

    # Test story start
    print("\n1. Testing story start notification...")
    notify_story_start(test_context)

    # Test story complete
    print("\n2. Testing story complete notification...")
    notify_story_complete(test_context)

    # Test error notification
    print("\n3. Testing error notification...")
    test_context.error = Exception("This is a test error")
    notify_error(test_context)

    # Test session end
    print("\n4. Testing session end notification...")
    notify_session_end(test_context)

    print("\nDone! Check your Slack channel for notifications.")
