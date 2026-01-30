/**
 * Messaging Bridge - Exposes autonomous coding skill to messaging channels
 * Integrates with Epiloop's command system for WhatsApp, Google Chat, etc.
 */

import type { AutonomousCodingSkill } from "./skill-handler.js";

export interface MessageContext {
  userId: string;
  channelId: string;
  messageId?: string;
  platform: "whatsapp" | "googlechat" | "telegram" | "discord" | "slack" | "other";
}

export interface MessagingBridge {
  handleMessage(message: string, context: MessageContext): Promise<string>;
  formatProgressUpdate(data: any): string;
  formatCompletionMessage(data: any): string;
  formatErrorMessage(error: Error): string;
}

/**
 * Create messaging bridge for autonomous coding skill
 */
export function createMessagingBridge(skill: AutonomousCodingSkill): MessagingBridge {
  return {
    async handleMessage(message: string, context: MessageContext): Promise<string> {
      // Parse command from message
      const command = parseCommand(message);

      if (!command) {
        return "Usage: /autonomous-coding <start|status|list|stop|resume> [options]";
      }

      try {
        const result = await skill.handleCommand(command.action, {
          ...command.params,
          userId: context.userId,
        });

        return formatCommandResult(result, command.action);
      } catch (error) {
        return `❌ Error: ${error instanceof Error ? error.message : String(error)}`;
      }
    },

    formatProgressUpdate(data: any): string {
      const { progress, currentStory, completedStories, totalStories } = data;
      return [
        `📊 Progress Update`,
        ``,
        `Progress: ${progress}%`,
        `Current: ${currentStory || "Starting..."}`,
        `Completed: ${completedStories}/${totalStories} stories`,
      ].join("\n");
    },

    formatCompletionMessage(data: any): string {
      const { sessionId, duration, completedStories, totalStories } = data;
      const minutes = Math.floor(duration / 60000);
      return [
        `🎉 Autonomous Implementation Complete!`,
        ``,
        `Session: ${sessionId}`,
        `Stories: ${completedStories}/${totalStories} completed`,
        `Duration: ${minutes} minutes`,
        ``,
        `All quality gates passed ✅`,
      ].join("\n");
    },

    formatErrorMessage(error: Error): string {
      return [
        `❌ Error in Autonomous Coding`,
        ``,
        error.message,
        ``,
        `Try: /autonomous-coding status to check session`,
      ].join("\n");
    },
  };
}

/**
 * Parse command from message
 */
function parseCommand(message: string): { action: string; params: Record<string, any> } | null {
  const trimmed = message.trim();

  // Match: /autonomous-coding start <description>
  const startMatch = trimmed.match(/^\/autonomous-coding\s+start\s+(.+)$/i);
  if (startMatch) {
    return {
      action: "start",
      params: { message: startMatch[1].trim() },
    };
  }

  // Match: /autonomous-coding status [--session <id>]
  const statusMatch = trimmed.match(/^\/autonomous-coding\s+status(?:\s+--session\s+([^\s]+))?$/i);
  if (statusMatch) {
    return {
      action: "status",
      params: statusMatch[1] ? { sessionId: statusMatch[1] } : {},
    };
  }

  // Match: /autonomous-coding list
  if (/^\/autonomous-coding\s+list$/i.test(trimmed)) {
    return {
      action: "list",
      params: {},
    };
  }

  // Match: /autonomous-coding stop --session <id>
  const stopMatch = trimmed.match(/^\/autonomous-coding\s+stop\s+--session\s+([^\s]+)$/i);
  if (stopMatch) {
    return {
      action: "stop",
      params: { sessionId: stopMatch[1] },
    };
  }

  // Match: /autonomous-coding resume --session <id>
  const resumeMatch = trimmed.match(/^\/autonomous-coding\s+resume\s+--session\s+([^\s]+)$/i);
  if (resumeMatch) {
    return {
      action: "resume",
      params: { sessionId: resumeMatch[1] },
    };
  }

  return null;
}

/**
 * Format command result for display
 */
function formatCommandResult(result: any, action: string): string {
  if (!result.success) {
    return `❌ ${result.message || "Command failed"}`;
  }

  switch (action) {
    case "start":
      return formatStartResult(result);
    case "status":
      return formatStatusResult(result);
    case "list":
      return formatListResult(result);
    case "stop":
      return `⏹ Session stopped. Checkpoint saved.`;
    case "resume":
      return `▶️ Session resumed from checkpoint.`;
    default:
      return `✅ ${result.message || "Command succeeded"}`;
  }
}

function formatStartResult(result: any): string {
  const lines = [
    `🚀 Autonomous Implementation Started`,
    ``,
    `Session ID: ${result.sessionId}`,
  ];

  if (result.prdPreview?.stories) {
    lines.push(`Stories: ${result.prdPreview.stories.length} identified`);
    lines.push(``);
    result.prdPreview.stories.slice(0, 3).forEach((story: any, i: number) => {
      lines.push(`${i + 1}. ${story.id}: ${story.title}`);
    });
    if (result.prdPreview.stories.length > 3) {
      lines.push(`... and ${result.prdPreview.stories.length - 3} more`);
    }
  }

  lines.push(``);
  lines.push(`💡 Track progress: /autonomous-coding status`);

  return lines.join("\n");
}

function formatStatusResult(result: any): string {
  const lines = [`📊 Session Status`];

  if (result.isRunning) {
    lines.push(``, `⚡️ Running`);
  } else {
    lines.push(``, `⏸ Stopped`);
  }

  if (result.progress) {
    lines.push(
      ``,
      `Progress: ${result.progress.percent}%`,
      `Current: ${result.progress.currentStory || "Starting..."}`,
      `Completed: ${result.progress.completedStories}/${result.progress.totalStories}`
    );
  }

  return lines.join("\n");
}

function formatListResult(result: any): string {
  if (!result.sessions || result.sessions.length === 0) {
    return `📋 No autonomous coding sessions found`;
  }

  const lines = [
    `📋 Your Autonomous Coding Sessions`,
    ``,
  ];

  result.sessions.forEach((session: any) => {
    const status = session.status === "running" ? "⚡️" : "⏹";
    lines.push(`${status} ${session.sessionId.substring(0, 8)}... - ${session.description}`);
  });

  return lines.join("\n");
}
