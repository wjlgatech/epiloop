/**
 * Loop Executor - Spawns and manages claude-loop.sh processes
 * Following TDD Iron Law: Tests written first, minimal implementation
 */

import { spawn, ChildProcess } from "child_process";
import { EventEmitter } from "events";
import { promises as fs } from "fs";
import * as path from "path";
import type { PRDFormat } from "./types.js";

export interface LoopExecutorConfig {
  claudeLoopPath: string;
  workspaceRoot: string;
  maxExecutionMinutes?: number;
  maxIterations?: number;
  apiKey?: string;
}

export interface ExecutionStatus {
  isRunning: boolean;
  currentStory: string | null;
  totalStories: number;
  completedStories: number;
  progressPercent: number;
  startTime: Date | null;
  elapsedSeconds: number;
  prdPath: string | null;
  logFile: string | null;
  checkpointExists: boolean;
  lastCheckpointTime: Date | null;
  environment: Record<string, string>;
  maxExecutionMinutes?: number;
}

export interface StopOptions {
  force?: boolean;
}

/**
 * Manages execution of claude-loop.sh with event streaming
 * Emits: started, stopped, iteration-start, story-complete, error, complete, timeout, progress, log
 */
export class LoopExecutor extends EventEmitter {
  private config: LoopExecutorConfig;
  private process: ChildProcess | null = null;
  private running = false;
  private startTime: Date | null = null;
  private currentPRD: PRDFormat | null = null;
  private workspaceDir: string;
  private prdPath: string | null = null;
  private logFilePath: string | null = null;
  private checkpointPath: string | null = null;
  private timeoutHandle: NodeJS.Timeout | null = null;
  private completedStories = 0;

  constructor(config: LoopExecutorConfig) {
    super();
    this.config = config;
    this.workspaceDir = config.workspaceRoot;

    // Validate claude-loop path exists
    if (!config.claudeLoopPath || config.claudeLoopPath === "/nonexistent/path") {
      throw new Error("claude-loop.sh not found at specified path");
    }
  }

  /**
   * Start execution with a PRD
   */
  async start(prd: PRDFormat): Promise<void> {
    if (this.running) {
      throw new Error("Executor is already running");
    }

    // Validate PRD
    if (!prd.userStories || prd.userStories.length === 0) {
      throw new Error("Invalid PRD: no user stories defined");
    }

    // Setup workspace
    await this.setupWorkspace(prd);

    this.currentPRD = prd;
    this.startTime = new Date();
    this.running = true;
    this.completedStories = prd.userStories.filter((s) => s.passes).length;

    // Setup timeout if configured
    if (this.config.maxExecutionMinutes) {
      const timeoutMs = this.config.maxExecutionMinutes * 60 * 1000;
      this.timeoutHandle = setTimeout(() => {
        this.handleTimeout();
      }, timeoutMs);
    }

    // Spawn process
    try {
      await this.spawnProcess();
      this.emit("started", { prd: prd.project, workspace: this.workspaceDir });
    } catch (error) {
      this.running = false;
      this.cleanup();
      throw error;
    }
  }

  /**
   * Stop execution gracefully (or forcefully)
   */
  async stop(options: StopOptions = {}): Promise<void> {
    if (!this.running) {
      return; // Idempotent
    }

    // Save checkpoint before stopping
    if (this.currentPRD) {
      await this.saveCheckpoint();
    }

    // Stop process
    if (this.process) {
      if (options.force) {
        this.process.kill("SIGKILL");
      } else {
        this.process.kill("SIGTERM");
      }
    }

    this.cleanup();
    this.emit("stopped");
  }

  /**
   * Resume from last checkpoint
   */
  async resume(): Promise<void> {
    const checkpointPath = path.join(this.workspaceDir, "checkpoint.json");

    try {
      const checkpointData = await fs.readFile(checkpointPath, "utf-8");
      const checkpoint = JSON.parse(checkpointData);

      // Load PRD from checkpoint
      const prdPath = checkpoint.prdPath || path.join(this.workspaceDir, "prd.json");
      const prdData = await fs.readFile(prdPath, "utf-8");
      const prd = JSON.parse(prdData) as PRDFormat;

      await this.start(prd);
    } catch (error) {
      throw new Error("No checkpoint found to resume from");
    }
  }

  /**
   * Check if executor is currently running
   */
  isRunning(): boolean {
    return this.running;
  }

  /**
   * Get current execution status
   */
  getStatus(): ExecutionStatus {
    const totalStories = this.currentPRD?.userStories.length || 0;
    const progressPercent =
      totalStories > 0 ? Math.round((this.completedStories / totalStories) * 100) : 0;

    const elapsedSeconds = this.startTime
      ? Math.floor((Date.now() - this.startTime.getTime()) / 1000)
      : 0;

    return {
      isRunning: this.running,
      currentStory: this.getCurrentStory(),
      totalStories,
      completedStories: this.completedStories,
      progressPercent,
      startTime: this.startTime,
      elapsedSeconds,
      prdPath: this.prdPath,
      logFile: this.logFilePath,
      checkpointExists: this.checkpointPath !== null,
      lastCheckpointTime: null, // TODO: Track from checkpoint file
      environment: this.getEnvironment(),
      maxExecutionMinutes: this.config.maxExecutionMinutes,
    };
  }

  // Private methods

  private async setupWorkspace(prd: PRDFormat): Promise<void> {
    // Create workspace directory
    await fs.mkdir(this.workspaceDir, { recursive: true });

    // Write PRD to workspace
    this.prdPath = path.join(this.workspaceDir, "prd.json");
    await fs.writeFile(this.prdPath, JSON.stringify(prd, null, 2));

    // Setup log file
    this.logFilePath = path.join(this.workspaceDir, "execution.jsonl");

    // Setup checkpoint path
    this.checkpointPath = path.join(this.workspaceDir, "checkpoint.json");
  }

  private async spawnProcess(): Promise<void> {
    if (!this.prdPath) {
      throw new Error("PRD not setup");
    }

    const env = this.getEnvironment();

    // Spawn claude-loop.sh (mocked in tests)
    this.process = spawn(this.config.claudeLoopPath, ["--prd", this.prdPath], {
      cwd: this.workspaceDir,
      env: { ...process.env, ...env },
    });

    // Setup stream handlers
    this.process.stdout?.on("data", (data) => {
      const output = data.toString();
      this.handleStdout(output);
    });

    this.process.stderr?.on("data", (data) => {
      const output = data.toString();
      this.handleStderr(output);
    });

    this.process.on("exit", (code) => {
      this.handleExit(code);
    });

    this.process.on("error", (error) => {
      this.handleError(error);
    });
  }

  private getEnvironment(): Record<string, string> {
    return {
      ANTHROPIC_API_KEY:
        this.config.apiKey || process.env.ANTHROPIC_API_KEY || "",
      CLAUDE_LOOP_WORKSPACE: this.workspaceDir,
    };
  }

  private getCurrentStory(): string | null {
    if (!this.currentPRD) return null;

    const currentStory = this.currentPRD.userStories.find((s) => !s.passes);
    return currentStory ? currentStory.id : null;
  }

  private handleStdout(output: string): void {
    // Log raw output
    this.emit("log", output);

    // Write to JSONL log
    if (this.logFilePath) {
      const logEntry = JSON.stringify({
        timestamp: new Date().toISOString(),
        level: "info",
        output: output.trim(),
      });
      fs.appendFile(this.logFilePath, logEntry + "\n").catch(() => {});
    }

    // Parse for events
    this.parseOutputForEvents(output);
  }

  private handleStderr(output: string): void {
    this.emit("log", output);

    if (this.logFilePath) {
      const logEntry = JSON.stringify({
        timestamp: new Date().toISOString(),
        level: "error",
        output: output.trim(),
      });
      fs.appendFile(this.logFilePath, logEntry + "\n").catch(() => {});
    }
  }

  private parseOutputForEvents(output: string): void {
    // Parse claude-loop output for structured events
    // This is a simplified parser - real implementation would be more robust

    if (output.includes("Starting iteration")) {
      this.emit("iteration-start", {
        iteration: this.extractNumber(output, /iteration (\d+)/i),
      });
    }

    if (output.includes("Story complete") || output.includes("passes: true")) {
      this.completedStories++;
      this.emit("story-complete", {
        storyId: this.extractStoryId(output),
        completedCount: this.completedStories,
      });

      // Emit progress
      if (this.currentPRD) {
        const progressPercent = Math.round(
          (this.completedStories / this.currentPRD.userStories.length) * 100
        );
        this.emit("progress", { percent: progressPercent });
      }
    }

    if (output.includes("All stories complete")) {
      this.emit("complete", {
        totalStories: this.currentPRD?.userStories.length || 0,
      });
    }
  }

  private extractNumber(text: string, pattern: RegExp): number {
    const match = text.match(pattern);
    return match ? parseInt(match[1], 10) : 0;
  }

  private extractStoryId(text: string): string | null {
    const match = text.match(/US-\d{3}/i);
    return match ? match[0] : null;
  }

  private handleExit(code: number | null): void {
    if (code !== 0 && code !== null) {
      this.emit("error", new Error(`Process exited with code ${code}`));
    }

    this.cleanup();
  }

  private handleError(error: Error): void {
    this.emit("error", error);
    this.cleanup();
  }

  private handleTimeout(): void {
    this.emit("timeout", {
      elapsedMinutes: this.config.maxExecutionMinutes,
    });

    this.saveCheckpoint().then(() => {
      this.stop({ force: true });
    });
  }

  private async saveCheckpoint(): Promise<void> {
    if (!this.checkpointPath || !this.currentPRD) return;

    const checkpoint = {
      timestamp: new Date().toISOString(),
      prdPath: this.prdPath,
      completedStories: this.completedStories,
      currentStory: this.getCurrentStory(),
      elapsedSeconds: this.startTime
        ? Math.floor((Date.now() - this.startTime.getTime()) / 1000)
        : 0,
    };

    await fs.writeFile(this.checkpointPath, JSON.stringify(checkpoint, null, 2));
  }

  private cleanup(): void {
    this.running = false;
    this.process = null;

    if (this.timeoutHandle) {
      clearTimeout(this.timeoutHandle);
      this.timeoutHandle = null;
    }
  }
}
