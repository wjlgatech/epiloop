/**
 * Autonomous Coding Skill Handler
 * Following TDD Iron Law: Tests written first, minimal implementation
 */

import { EventEmitter } from "events";
import { randomUUID } from "crypto";
import { LoopExecutor } from "./loop-executor.js";
import { ProgressReporter } from "./progress-reporter.js";
import { convertMessageToPRD } from "./prd-generator.js";
import type { PRDFormat, CodebaseContext } from "./types.js";

export interface SkillConfig {
  workspaceRoot: string;
  claudeLoopPath: string;
  maxConcurrentSessions?: number;
}

export interface Session {
  sessionId: string;
  userId: string;
  description: string;
  executor: LoopExecutor;
  reporter: ProgressReporter;
  prd: PRDFormat;
  startTime: Date;
  status: "running" | "stopped" | "completed" | "error";
}

export interface CommandResult {
  success: boolean;
  message?: string;
  sessionId?: string;
  prdPreview?: PRDFormat;
  isRunning?: boolean;
  progress?: {
    percent: number;
    currentStory: string | null;
    completedStories: number;
    totalStories: number;
  };
  currentStory?: string | null;
  checkpointExists?: boolean;
  sessions?: Array<{
    sessionId: string;
    userId: string;
    description: string;
    startTime: Date;
    status: string;
  }>;
}

/**
 * Handles autonomous coding skill commands
 * Emits: progress, story-complete, complete, error
 */
export class AutonomousCodingSkill extends EventEmitter {
  private config: SkillConfig;
  private sessions: Map<string, Session> = new Map();
  private userSessions: Map<string, Set<string>> = new Map();

  constructor(config: SkillConfig) {
    super();
    this.config = config;
  }

  /**
   * Handle skill commands
   */
  async handleCommand(
    command: string,
    params: any
  ): Promise<CommandResult> {
    try {
      switch (command) {
        case "start":
          return await this.handleStart(params);
        case "stop":
          return await this.handleStop(params);
        case "status":
          return await this.handleStatus(params);
        case "resume":
          return await this.handleResume(params);
        case "list":
          return await this.handleList(params);
        default:
          return {
            success: false,
            message: `Unknown command: ${command}`,
          };
      }
    } catch (error) {
      return {
        success: false,
        message: error instanceof Error ? error.message : String(error),
      };
    }
  }

  /**
   * Stop all running sessions
   */
  async stopAll(): Promise<void> {
    for (const session of this.sessions.values()) {
      if (session.status === "running") {
        await session.executor.stop();
      }
    }
  }

  // Private command handlers

  private async handleStart(params: {
    description?: string;
    message?: string;
    userId: string;
    verbosity?: "minimal" | "normal" | "detailed";
    context?: CodebaseContext;
  }): Promise<CommandResult> {
    const description = params.description || params.message || "";
    const { userId, verbosity = "normal", context } = params;

    // Validate description
    if (!description || description.trim().length === 0) {
      return {
        success: false,
        message: "Description cannot be empty",
      };
    }

    // Check if user already has active session
    const userSessionIds = this.userSessions.get(userId) || new Set();
    for (const sessionId of userSessionIds) {
      const session = this.sessions.get(sessionId);
      if (session && session.status === "running") {
        return {
          success: false,
          message: `You already have an active session (${sessionId}). Stop it first or use 'status' to check progress.`,
        };
      }
    }

    // Generate PRD from description
    const prd = await convertMessageToPRD(description, context);

    // Create session
    const sessionId = randomUUID();
    const workspaceDir = `${this.config.workspaceRoot}/${sessionId}`;

    const executor = new LoopExecutor({
      claudeLoopPath: this.config.claudeLoopPath,
      workspaceRoot: workspaceDir,
      maxExecutionMinutes: 120, // 2 hours default
    });

    const reporter = new ProgressReporter({ verbosity });

    // Setup event forwarding
    this.setupEventForwarding(sessionId, executor, reporter);

    // Subscribe reporter to executor
    reporter.subscribe(executor);

    // Create session record
    const session: Session = {
      sessionId,
      userId,
      description,
      executor,
      reporter,
      prd,
      startTime: new Date(),
      status: "running",
    };

    this.sessions.set(sessionId, session);

    // Track user sessions
    if (!this.userSessions.has(userId)) {
      this.userSessions.set(userId, new Set());
    }
    this.userSessions.get(userId)!.add(sessionId);

    // Start execution (don't await - run in background)
    executor
      .start(prd)
      .then(() => {
        session.status = "completed";
        this.emit("complete", { sessionId, userId });
      })
      .catch((error) => {
        session.status = "error";
        this.emit("error", { sessionId, userId, error });
      });

    return {
      success: true,
      message: `Started autonomous implementation of "${description}"`,
      sessionId,
      prdPreview: prd,
    };
  }

  private async handleStop(params: {
    sessionId: string;
    userId: string;
  }): Promise<CommandResult> {
    const { sessionId, userId } = params;

    const session = this.sessions.get(sessionId);
    if (!session) {
      return {
        success: false,
        message: "Session not found",
      };
    }

    // Check authorization
    if (session.userId !== userId) {
      return {
        success: false,
        message: "You are not authorized to stop this session",
      };
    }

    // Stop executor
    await session.executor.stop();
    session.status = "stopped";

    return {
      success: true,
      message: "Execution stopped and checkpoint saved",
    };
  }

  private async handleStatus(params: {
    sessionId: string;
    userId: string;
  }): Promise<CommandResult> {
    const { sessionId, userId } = params;

    const session = this.sessions.get(sessionId);
    if (!session) {
      return {
        success: false,
        message: "Session not found",
      };
    }

    // Check authorization
    if (session.userId !== userId) {
      return {
        success: false,
        message: "You are not authorized to view this session",
      };
    }

    const status = session.executor.getStatus();

    return {
      success: true,
      isRunning: status.isRunning,
      progress: {
        percent: status.progressPercent,
        currentStory: status.currentStory,
        completedStories: status.completedStories,
        totalStories: status.totalStories,
      },
      currentStory: status.currentStory,
      checkpointExists: status.checkpointExists,
    };
  }

  private async handleResume(params: {
    sessionId: string;
    userId: string;
  }): Promise<CommandResult> {
    const { sessionId, userId } = params;

    const session = this.sessions.get(sessionId);
    if (!session) {
      return {
        success: false,
        message: "Session not found",
      };
    }

    // Check authorization
    if (session.userId !== userId) {
      return {
        success: false,
        message: "You are not authorized to resume this session",
      };
    }

    // Check if checkpoint exists
    const status = session.executor.getStatus();
    if (!status.checkpointExists) {
      return {
        success: false,
        message: "No checkpoint found to resume from",
      };
    }

    // Resume execution
    try {
      await session.executor.resume();
      session.status = "running";

      return {
        success: true,
        message: "Execution resumed from checkpoint",
      };
    } catch (error) {
      return {
        success: false,
        message: error instanceof Error ? error.message : String(error),
      };
    }
  }

  private async handleList(params: {
    userId: string;
  }): Promise<CommandResult> {
    const { userId } = params;

    const userSessionIds = this.userSessions.get(userId) || new Set();
    const sessions = Array.from(userSessionIds)
      .map((sessionId) => this.sessions.get(sessionId))
      .filter((s): s is Session => s !== undefined)
      .map((session) => ({
        sessionId: session.sessionId,
        userId: session.userId,
        description: session.description,
        startTime: session.startTime,
        status: session.status,
      }));

    return {
      success: true,
      sessions,
    };
  }

  private setupEventForwarding(
    sessionId: string,
    executor: LoopExecutor,
    reporter: ProgressReporter
  ): void {
    // Forward executor events
    executor.on("started", (data) => {
      this.emit("started", { sessionId, ...data });
    });

    executor.on("story-complete", (data) => {
      this.emit("story-complete", { sessionId, ...data });
    });

    executor.on("progress", (data) => {
      this.emit("progress", { sessionId, ...data });
    });

    executor.on("complete", (data) => {
      this.emit("complete", { sessionId, ...data });
    });

    executor.on("error", (error) => {
      this.emit("error", { sessionId, error });
    });

    // Forward reporter messages
    reporter.on("message", (message) => {
      this.emit("message", { sessionId, message });
    });
  }
}
