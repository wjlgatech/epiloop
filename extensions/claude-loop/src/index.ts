import type { EpiloopPluginApi } from "epiloop/plugin-sdk";
import { emptyPluginConfigSchema } from "epiloop/plugin-sdk";
import { AutonomousCodingSkill } from "./skill-handler.js";
import { loadConfig } from "./config.js";
import { createMessagingBridge } from "./messaging-bridge.js";
import type { MessageContext } from "./messaging-bridge.js";
import * as path from "path";

/**
 * Claude-loop autonomous coding agent integration plugin
 *
 * This plugin enables users to request feature implementations via conversational
 * channels (WhatsApp, Telegram, etc.) that execute autonomously with quality gates
 * and progress reporting.
 */
const claudeLoopPlugin = {
  id: "claude-loop",
  name: "Claude Loop Autonomous Coding",
  description: "Autonomous feature implementation with Reality-Grounded TDD",
  version: "2026.1.29",
  configSchema: emptyPluginConfigSchema(),

  register(api: EpiloopPluginApi) {
    api.runtime.logger.info("Claude Loop plugin registering...");

    try {
      // Load configuration
      const config = loadConfig();
      api.runtime.logger.info("Configuration loaded", {
        maxConcurrent: config.execution.maxConcurrent,
        workspaceRoot: config.claudeLoop.workspaceRoot,
      });

      // Initialize autonomous coding skill
      const skill = new AutonomousCodingSkill({
        workspaceRoot: config.claudeLoop.workspaceRoot,
        claudeLoopPath: path.join(config.claudeLoop.path, "claude-loop.sh"),
        maxConcurrentSessions: config.workspace.maxConcurrentPerUser,
      });

      // Create messaging bridge for WhatsApp/Google Chat integration
      const messagingBridge = createMessagingBridge(skill);

      // Forward skill events to logger and messaging channels
      skill.on("progress", ({ sessionId, progress, currentStory, completedStories, totalStories }) => {
        api.runtime.logger.info(`[${sessionId}] Progress: ${progress}% - ${currentStory || "starting"}`);

        // Send progress update to messaging channels
        const progressMessage = messagingBridge.formatProgressUpdate({
          progress,
          currentStory,
          completedStories,
          totalStories,
        });
        // TODO: Send progressMessage to appropriate messaging channel
      });

      skill.on("story-complete", ({ sessionId, storyId, duration }) => {
        api.runtime.logger.info(`[${sessionId}] Story ${storyId} completed in ${duration}ms`);
      });

      skill.on("complete", ({ sessionId, duration, completedStories, totalStories }) => {
        api.runtime.logger.info(`[${sessionId}] Autonomous implementation completed in ${duration}ms`);

        // Send completion message to messaging channels
        const completionMessage = messagingBridge.formatCompletionMessage({
          sessionId,
          duration,
          completedStories,
          totalStories,
        });
        // TODO: Send completionMessage to appropriate messaging channel
      });

      skill.on("error", ({ sessionId, error }) => {
        api.runtime.logger.error(`[${sessionId}] Error:`, error);

        // Send error message to messaging channels
        const errorMessage = messagingBridge.formatErrorMessage(error);
        // TODO: Send errorMessage to appropriate messaging channel
      });

      // Register skill with Epiloop
      // Make skill available globally for CLI/API access
      (api as any).autonomousCoding = skill;

      // Register command handler if Epiloop supports it
      if ((api as any).commands) {
        (api as any).commands.register("autonomous-coding", async (command: string, params: any) => {
          return await skill.handleCommand(command, params);
        });
      }

      // Register messaging handler for WhatsApp/Google Chat conversational access
      if ((api as any).messaging?.registerHandler) {
        (api as any).messaging.registerHandler(
          "autonomous-coding",
          async (message: string, context: MessageContext) => {
            try {
              const response = await messagingBridge.handleMessage(message, context);
              return response;
            } catch (error) {
              return messagingBridge.formatErrorMessage(
                error instanceof Error ? error : new Error(String(error))
              );
            }
          }
        );
        api.runtime.logger.info("Messaging handler registered for /autonomous-coding");
      }

      api.runtime.logger.info("Claude Loop plugin registered successfully", {
        skillRegistered: true,
        workspaceRoot: config.claudeLoop.workspaceRoot,
      });
    } catch (error) {
      api.runtime.logger.error("Failed to register Claude Loop plugin:", error);
      throw error;
    }
  },

  deactivate() {
    // Cleanup on plugin deactivation
    // Stop all running sessions, cleanup resources, etc.
  },
};

export default claudeLoopPlugin;

// Export types and utilities for external use
export { AutonomousCodingSkill } from "./skill-handler.js";
export { LoopExecutor } from "./loop-executor.js";
export { ProgressReporter } from "./progress-reporter.js";
export { convertMessageToPRD } from "./prd-generator.js";
export { createMessagingBridge } from "./messaging-bridge.js";
export type { PRDFormat, UserStory, CodebaseContext } from "./types.js";
export type { MessagingBridge, MessageContext } from "./messaging-bridge.js";
