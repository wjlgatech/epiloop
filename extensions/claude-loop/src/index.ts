import type { ClawdbotPluginApi } from "clawdbot/plugin-sdk";
import { emptyPluginConfigSchema } from "clawdbot/plugin-sdk";

/**
 * Claude-loop autonomous coding agent integration plugin
 *
 * This plugin enables users to request feature implementations via conversational
 * channels (WhatsApp, Telegram, etc.) that execute autonomously with quality gates
 * and progress reporting.
 */
const claudeLoopPlugin = {
  id: "claude-loop",
  name: "Claude Loop",
  description: "Autonomous coding agent for feature implementation",
  configSchema: emptyPluginConfigSchema(),
  register(api: ClawdbotPluginApi) {
    // Plugin registration logic will be implemented in subsequent user stories
    // US-003: PRD generator
    // US-004: Loop executor with progress streaming
    // US-005: Progress reporter for messaging channels
    // US-006: Skill integration
    api.runtime.logger.info("Claude Loop plugin registered");
  },
};

export default claudeLoopPlugin;
