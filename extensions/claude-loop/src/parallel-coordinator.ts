/**
 * Parallel Execution Coordinator
 * Manages multiple concurrent autonomous coding tasks with resource limits
 */

import { EventEmitter } from "events";
import { LoopExecutor } from "./loop-executor.js";
import type { PRDFormat } from "./types.js";

export interface ParallelCoordinatorConfig {
  claudeLoopPath: string; // Path to claude-loop.sh
  workspaceRoot: string; // Root directory for workspaces
  maxConcurrent?: number; // Max concurrent tasks
  maxMemoryPerTask?: number; // MB per task
  maxCpuPerTask?: number; // % CPU per task
}

export interface TaskInfo {
  id: string;
  prd: PRDFormat;
  userId: string;
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  executor?: LoopExecutor;
  startedAt?: Date;
  completedAt?: Date;
  error?: string;
  progress?: number;
}

export interface CoordinatorStats {
  active: number;
  queued: number;
  completed: number;
  failed: number;
  cancelled: number;
}

/**
 * Coordinates parallel execution of multiple autonomous coding tasks
 *
 * Events:
 * - task-started: { taskId, userId }
 * - task-progress: { taskId, progress, currentStory }
 * - task-completed: { taskId, userId, duration }
 * - task-error: { taskId, error }
 * - task-cancelled: { taskId }
 */
export class ParallelCoordinator extends EventEmitter {
  private config: Required<ParallelCoordinatorConfig>;
  private tasks: Map<string, TaskInfo> = new Map();
  private queue: string[] = [];
  private taskCounter = 0;

  constructor(config: ParallelCoordinatorConfig) {
    super();
    this.config = {
      claudeLoopPath: config.claudeLoopPath,
      workspaceRoot: config.workspaceRoot,
      maxConcurrent: config.maxConcurrent ?? 3,
      maxMemoryPerTask: config.maxMemoryPerTask ?? 512,
      maxCpuPerTask: config.maxCpuPerTask ?? 50,
    };
  }

  /**
   * Enqueue a new task for execution
   */
  async enqueue(prd: PRDFormat, userId: string): Promise<string> {
    const taskId = `task-${++this.taskCounter}-${Date.now()}`;

    const taskInfo: TaskInfo = {
      id: taskId,
      prd,
      userId,
      status: "queued",
    };

    this.tasks.set(taskId, taskInfo);
    this.queue.push(taskId);

    // Try to start task immediately if under capacity
    setImmediate(() => this.processQueue());

    return taskId;
  }

  /**
   * Cancel a task (works for queued and running tasks)
   */
  async cancel(taskId: string): Promise<boolean> {
    const task = this.tasks.get(taskId);
    if (!task) {
      return false;
    }

    if (task.status === "queued") {
      // Remove from queue
      const queueIndex = this.queue.indexOf(taskId);
      if (queueIndex !== -1) {
        this.queue.splice(queueIndex, 1);
      }
      task.status = "cancelled";
      task.completedAt = new Date();
      this.emit("task-cancelled", { taskId });
      return true;
    }

    if (task.status === "running" && task.executor) {
      // Stop running executor
      await task.executor.stop({ force: false });
      task.status = "cancelled";
      task.completedAt = new Date();
      this.emit("task-cancelled", { taskId });
      return true;
    }

    return false;
  }

  /**
   * Get status of a specific task
   */
  getTaskStatus(taskId: string): TaskInfo | undefined {
    return this.tasks.get(taskId);
  }

  /**
   * List all tasks (optionally filtered by user)
   */
  listTasks(userId?: string): TaskInfo[] {
    const allTasks = Array.from(this.tasks.values());
    if (userId) {
      return allTasks.filter((t) => t.userId === userId);
    }
    return allTasks;
  }

  /**
   * Get coordinator statistics
   */
  getStats(): CoordinatorStats {
    const tasks = Array.from(this.tasks.values());
    return {
      active: tasks.filter((t) => t.status === "running").length,
      queued: tasks.filter((t) => t.status === "queued").length,
      completed: tasks.filter((t) => t.status === "completed").length,
      failed: tasks.filter((t) => t.status === "failed").length,
      cancelled: tasks.filter((t) => t.status === "cancelled").length,
    };
  }

  /**
   * Shutdown coordinator gracefully
   */
  async shutdown(): Promise<void> {
    // Stop all running tasks
    const runningTasks = Array.from(this.tasks.values()).filter(
      (t) => t.status === "running"
    );

    await Promise.all(
      runningTasks.map(async (task) => {
        if (task.executor) {
          await task.executor.stop({ force: false });
        }
      })
    );

    // Clear queue
    this.queue = [];
  }

  /**
   * Process the queue - start tasks up to maxConcurrent
   */
  private processQueue(): void {
    const stats = this.getStats();

    // Don't start new tasks if at capacity
    if (stats.active >= this.config.maxConcurrent) {
      return;
    }

    // Start next queued task
    while (this.queue.length > 0 && stats.active < this.config.maxConcurrent) {
      const taskId = this.queue.shift();
      if (!taskId) break;

      const task = this.tasks.get(taskId);
      if (!task || task.status !== "queued") continue;

      this.startTask(task);
    }
  }

  /**
   * Start executing a task
   */
  private async startTask(task: TaskInfo): Promise<void> {
    task.status = "running";
    task.startedAt = new Date();

    this.emit("task-started", {
      taskId: task.id,
      userId: task.userId,
    });

    try {
      // Create executor
      const executor = new LoopExecutor({
        claudeLoopPath: this.config.claudeLoopPath,
        workspaceRoot: `${this.config.workspaceRoot}/${task.id}`,
        maxExecutionMinutes: 60, // 1 hour
      });

      task.executor = executor;

      // Forward progress events
      executor.on("progress", (data) => {
        task.progress = data.progress;
        this.emit("task-progress", {
          taskId: task.id,
          progress: data.progress,
          currentStory: data.currentStory,
        });
      });

      // Execute
      await executor.start(task.prd);

      // Task completed
      task.status = "completed";
      task.completedAt = new Date();

      const duration = task.completedAt.getTime() - (task.startedAt?.getTime() || 0);

      this.emit("task-completed", {
        taskId: task.id,
        userId: task.userId,
        duration,
      });
    } catch (error) {
      // Task failed
      task.status = "failed";
      task.completedAt = new Date();
      task.error = error instanceof Error ? error.message : String(error);

      this.emit("task-error", {
        taskId: task.id,
        error: task.error,
      });
    } finally {
      // Process next queued task
      setImmediate(() => this.processQueue());
    }
  }
}
