/**
 * Progress Reporter - Formats executor events into human-readable messages
 * Following TDD Iron Law: Tests written first, minimal implementation
 */

import { EventEmitter } from "events";
import type { LoopExecutor } from "./loop-executor.js";

export type VerbosityLevel = "minimal" | "normal" | "detailed";

export interface ProgressReporterConfig {
  verbosity?: VerbosityLevel;
  batchDelayMs?: number;
}

interface BatchedUpdate {
  type: string;
  data: any;
  timestamp: number;
}

/**
 * Converts technical executor events into user-friendly messages
 * Emits 'message' events with formatted strings
 */
export class ProgressReporter extends EventEmitter {
  private config: ProgressReporterConfig;
  private executor: LoopExecutor | null = null;
  private batchBuffer: BatchedUpdate[] = [];
  private batchTimer: NodeJS.Timeout | null = null;
  private eventHandlers: Map<string, Function> = new Map();

  constructor(config: ProgressReporterConfig = {}) {
    super();
    this.config = {
      verbosity: config.verbosity || "normal",
      batchDelayMs: config.batchDelayMs || 2000,
    };
  }

  /**
   * Subscribe to executor events
   */
  subscribe(executor: LoopExecutor): void {
    // Unsubscribe if already subscribed
    if (this.executor) {
      this.unsubscribe();
    }

    this.executor = executor;

    // Setup event handlers
    this.setupHandler("started", this.handleStarted.bind(this));
    this.setupHandler("stopped", this.handleStopped.bind(this));
    this.setupHandler("iteration-start", this.handleIterationStart.bind(this));
    this.setupHandler("story-complete", this.handleStoryComplete.bind(this));
    this.setupHandler("progress", this.handleProgress.bind(this));
    this.setupHandler("error", this.handleError.bind(this));
    this.setupHandler("complete", this.handleComplete.bind(this));
    this.setupHandler("timeout", this.handleTimeout.bind(this));
  }

  /**
   * Unsubscribe from executor events
   */
  unsubscribe(): void {
    if (!this.executor) return;

    // Remove all handlers
    this.eventHandlers.forEach((handler, event) => {
      this.executor?.removeListener(event, handler as any);
    });

    this.eventHandlers.clear();
    this.executor = null;

    // Clear batch timer
    if (this.batchTimer) {
      clearTimeout(this.batchTimer);
      this.batchTimer = null;
    }
  }

  // Private methods

  private setupHandler(event: string, handler: Function): void {
    if (!this.executor) return;

    this.executor.on(event, handler as any);
    this.eventHandlers.set(event, handler);
  }

  private handleStarted(data: any): void {
    const { prd, workspace } = data;
    let message = "";

    switch (this.config.verbosity) {
      case "minimal":
        message = `🚀 Starting: ${prd}`;
        break;
      case "detailed":
        message = `🚀 Started autonomous coding\nProject: ${prd}\nWorkspace: ${workspace}`;
        break;
      default: // normal
        message = `🚀 Starting autonomous implementation of "${prd}"`;
    }

    this.emitMessage(message);
  }

  private handleStopped(): void {
    const message =
      this.config.verbosity === "minimal"
        ? "⏸️ Stopped"
        : "⏸️ Execution stopped";

    this.emitMessage(message);
  }

  private handleIterationStart(data: any): void {
    if (this.config.verbosity !== "detailed") {
      return; // Only show in detailed mode
    }

    const { iteration } = data;
    this.emitMessage(`🔄 Iteration ${iteration} started`);
  }

  private handleStoryComplete(data: any): void {
    const { storyId, completedCount } = data;

    let message = "";
    switch (this.config.verbosity) {
      case "minimal":
        message = `✅ ${storyId}`;
        break;
      case "detailed":
        message = `✅ Story ${storyId} complete (${completedCount} total completed)`;
        break;
      default: // normal
        message = `✅ Completed ${storyId}`;
    }

    this.emitMessage(message);
  }

  private handleProgress(data: any): void {
    const { percent } = data;

    // Batch progress updates (non-critical)
    this.batchUpdate("progress", data);
  }

  private handleError(error: Error): void {
    const errorMsg = error.message;
    let message = `❌ Error: ${errorMsg}`;

    // Add actionable guidance for common errors
    if (errorMsg.toLowerCase().includes("rate limit")) {
      message += "\n💡 Tip: Wait a few minutes and try again";
    } else if (errorMsg.toLowerCase().includes("api key")) {
      message += "\n💡 Tip: Check your ANTHROPIC_API_KEY environment variable";
    } else if (errorMsg.toLowerCase().includes("timeout")) {
      message += "\n💡 Tip: The task may be too complex. Consider breaking it into smaller stories";
    }

    // Truncate very long errors
    if (message.length > 400) {
      message = message.substring(0, 397) + "...";
    }

    // Critical - emit immediately
    this.emitMessage(message);
  }

  private handleComplete(data: any): void {
    const { totalStories, duration, prUrl, testsAdded, testsPassed, coverage, filesChanged } = data;

    let message = "🎉 Implementation Complete!\n";

    // Basic summary
    message += `✅ ${totalStories} ${totalStories === 1 ? "story" : "stories"} completed`;

    // Duration
    if (duration) {
      const durationStr = this.formatDuration(duration);
      message += `\n⏱️ Time: ${durationStr}`;
    }

    // PR link
    if (prUrl) {
      message += `\n🔗 Pull Request: ${prUrl}`;
    }

    // Test results
    if (testsAdded !== undefined) {
      message += `\n🧪 Tests: ${testsAdded} added`;
      if (testsPassed !== undefined) {
        message += `, ${testsPassed} passing`;
      }
      if (coverage !== undefined) {
        message += `, ${coverage}% coverage`;
      }
    }

    // Files changed (detailed only)
    if (this.config.verbosity === "detailed" && filesChanged && filesChanged.length > 0) {
      const fileList =
        filesChanged.length > 5
          ? filesChanged.slice(0, 5).join(", ") + `, and ${filesChanged.length - 5} more`
          : filesChanged.join(", ");
      message += `\n📝 Files: ${fileList}`;
    }

    this.emitMessage(message);
  }

  private handleTimeout(data: any): void {
    const { elapsedMinutes } = data;
    const message = `⏱️ Timeout reached (${elapsedMinutes} minutes). Execution stopped and checkpoint saved.`;

    this.emitMessage(message);
  }

  private batchUpdate(type: string, data: any): void {
    // Add to batch buffer
    this.batchBuffer.push({
      type,
      data,
      timestamp: Date.now(),
    });

    // Clear existing timer
    if (this.batchTimer) {
      clearTimeout(this.batchTimer);
    }

    // Set new timer
    this.batchTimer = setTimeout(() => {
      this.flushBatch();
    }, this.config.batchDelayMs);
  }

  private flushBatch(): void {
    if (this.batchBuffer.length === 0) return;

    // Group by type
    const byType = new Map<string, BatchedUpdate[]>();
    for (const update of this.batchBuffer) {
      const list = byType.get(update.type) || [];
      list.push(update);
      byType.set(update.type, list);
    }

    // Process each type
    byType.forEach((updates, type) => {
      if (type === "progress") {
        // Only emit the latest progress
        const latest = updates[updates.length - 1];
        this.emitProgressMessage(latest.data);
      }
    });

    // Clear buffer
    this.batchBuffer = [];
    this.batchTimer = null;
  }

  private emitProgressMessage(data: any): void {
    const { percent } = data;

    if (this.config.verbosity === "minimal") {
      // Skip in minimal mode
      return;
    }

    let message = "";
    if (this.config.verbosity === "detailed") {
      // Progress bar
      const bar = this.createProgressBar(percent);
      message = `⚡ Progress: ${bar} ${percent}%`;
    } else {
      // Simple percentage
      message = `⚡ ${percent}% complete`;
    }

    this.emitMessage(message);
  }

  private createProgressBar(percent: number, width: number = 20): string {
    const filled = Math.round((percent / 100) * width);
    const empty = width - filled;
    return "█".repeat(filled) + "░".repeat(empty);
  }

  private formatDuration(seconds: number): string {
    if (seconds < 60) {
      return `${seconds}s`;
    } else if (seconds < 3600) {
      const minutes = Math.floor(seconds / 60);
      const remainingSeconds = seconds % 60;
      return remainingSeconds > 0
        ? `${minutes}m ${remainingSeconds}s`
        : `${minutes}m`;
    } else {
      const hours = Math.floor(seconds / 3600);
      const minutes = Math.floor((seconds % 3600) / 60);
      return minutes > 0 ? `${hours}h ${minutes}m` : `${hours}h`;
    }
  }

  private emitMessage(message: string): void {
    // Ensure message is not too long
    if (message.length > 450) {
      message = message.substring(0, 447) + "...";
    }

    this.emit("message", message);
  }
}
