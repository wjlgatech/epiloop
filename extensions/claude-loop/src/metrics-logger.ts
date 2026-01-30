/**
 * Metrics Logger - Comprehensive logging and metrics for autonomous coding sessions
 * Tracks execution progress, resource usage, quality gates, and errors
 */

import * as fs from "fs";
import * as path from "path";

export interface SessionStartMetadata {
  userId: string;
  prdTitle: string;
  totalStories: number;
}

export interface StoryProgress {
  storyId: string;
  status: "in_progress" | "completed" | "failed";
  duration?: number;
  timestamp?: Date;
}

export interface ErrorLog {
  message: string;
  stack?: string;
  phase: string;
  timestamp?: Date;
}

export interface QualityGateLog {
  storyId: string;
  gate: string;
  passed: boolean;
  coverage?: number;
  timestamp?: Date;
}

export interface ResourceUsageLog {
  cpu: number;
  memory: number;
  timestamp: Date;
}

export interface SessionMetrics {
  sessionId: string;
  userId: string;
  prdTitle: string;
  totalStories: number;
  startedAt: Date;
  completedAt?: Date;
  stories: StoryProgress[];
  errors: ErrorLog[];
  qualityGates: QualityGateLog[];
  resourceUsage: ResourceUsageLog[];
}

export interface AggregateStats {
  totalStories: number;
  completedStories: number;
  failedStories: number;
  averageDuration: number;
  totalDuration: number;
  errorCount: number;
  qualityGatePassRate: number;
}

export interface SessionSummary {
  sessionId: string;
  userId: string;
  prdTitle: string;
  startedAt: Date;
  completedAt?: Date;
  status: "in_progress" | "completed" | "failed";
}

export interface ListOptions {
  userId?: string;
  status?: "in_progress" | "completed" | "failed";
  limit?: number;
}

/**
 * Logger for tracking metrics and progress of autonomous coding sessions
 */
export class MetricsLogger {
  private metricsDir: string;
  private sessions: Map<string, SessionMetrics> = new Map();

  constructor(metricsDir: string) {
    this.metricsDir = metricsDir;

    // Create metrics directory if it doesn't exist
    if (!fs.existsSync(metricsDir)) {
      fs.mkdirSync(metricsDir, { recursive: true });
    }

    // Load existing metrics from disk
    this.loadMetricsFromDisk();
  }

  /**
   * Log the start of an execution session
   */
  async logExecutionStart(
    sessionId: string,
    metadata: SessionStartMetadata
  ): Promise<void> {
    const metrics: SessionMetrics = {
      sessionId,
      userId: metadata.userId,
      prdTitle: metadata.prdTitle,
      totalStories: metadata.totalStories,
      startedAt: new Date(),
      stories: [],
      errors: [],
      qualityGates: [],
      resourceUsage: [],
    };

    this.sessions.set(sessionId, metrics);
    await this.persistMetrics(sessionId);
  }

  /**
   * Log story progress
   */
  async logStoryProgress(
    sessionId: string,
    progress: StoryProgress
  ): Promise<void> {
    const metrics = this.sessions.get(sessionId);
    if (!metrics) {
      throw new Error(`Session ${sessionId} not found`);
    }

    // Update existing story or add new one
    const existingIndex = metrics.stories.findIndex(
      (s) => s.storyId === progress.storyId
    );

    const storyData = {
      ...progress,
      timestamp: progress.timestamp || new Date(),
    };

    if (existingIndex !== -1) {
      metrics.stories[existingIndex] = storyData;
    } else {
      metrics.stories.push(storyData);
    }

    await this.persistMetrics(sessionId);
  }

  /**
   * Log an error
   */
  async logError(sessionId: string, error: ErrorLog): Promise<void> {
    const metrics = this.sessions.get(sessionId);
    if (!metrics) {
      throw new Error(`Session ${sessionId} not found`);
    }

    metrics.errors.push({
      ...error,
      timestamp: error.timestamp || new Date(),
    });

    await this.persistMetrics(sessionId);
  }

  /**
   * Log quality gate result
   */
  async logQualityGate(
    sessionId: string,
    gateResult: QualityGateLog
  ): Promise<void> {
    const metrics = this.sessions.get(sessionId);
    if (!metrics) {
      throw new Error(`Session ${sessionId} not found`);
    }

    metrics.qualityGates.push({
      ...gateResult,
      timestamp: gateResult.timestamp || new Date(),
    });

    await this.persistMetrics(sessionId);
  }

  /**
   * Log resource usage
   */
  async logResourceUsage(
    sessionId: string,
    usage: ResourceUsageLog
  ): Promise<void> {
    const metrics = this.sessions.get(sessionId);
    if (!metrics) {
      throw new Error(`Session ${sessionId} not found`);
    }

    metrics.resourceUsage.push(usage);
    await this.persistMetrics(sessionId);
  }

  /**
   * Get metrics for a session
   */
  async getSessionMetrics(sessionId: string): Promise<SessionMetrics | undefined> {
    return this.sessions.get(sessionId);
  }

  /**
   * Get aggregate statistics for a session
   */
  async getAggregateStats(sessionId: string): Promise<AggregateStats | undefined> {
    const metrics = this.sessions.get(sessionId);
    if (!metrics) {
      return undefined;
    }

    const completedStories = metrics.stories.filter(
      (s) => s.status === "completed"
    );
    const failedStories = metrics.stories.filter((s) => s.status === "failed");

    const durations = completedStories
      .map((s) => s.duration)
      .filter((d): d is number => d !== undefined);

    const averageDuration =
      durations.length > 0
        ? durations.reduce((a, b) => a + b, 0) / durations.length
        : 0;

    const totalDuration = durations.reduce((a, b) => a + b, 0);

    const passedGates = metrics.qualityGates.filter((g) => g.passed).length;
    const qualityGatePassRate =
      metrics.qualityGates.length > 0
        ? passedGates / metrics.qualityGates.length
        : 0;

    return {
      totalStories: metrics.stories.length,
      completedStories: completedStories.length,
      failedStories: failedStories.length,
      averageDuration,
      totalDuration,
      errorCount: metrics.errors.length,
      qualityGatePassRate,
    };
  }

  /**
   * Export metrics as JSON string
   */
  async exportMetrics(sessionId: string): Promise<string | undefined> {
    const metrics = this.sessions.get(sessionId);
    if (!metrics) {
      return undefined;
    }

    return JSON.stringify(metrics, null, 2);
  }

  /**
   * List all sessions
   */
  async listSessions(options: ListOptions = {}): Promise<SessionSummary[]> {
    let sessions = Array.from(this.sessions.values());

    // Filter by userId if specified
    if (options.userId) {
      sessions = sessions.filter((s) => s.userId === options.userId);
    }

    // Map to summaries
    const summaries: SessionSummary[] = sessions.map((s) => ({
      sessionId: s.sessionId,
      userId: s.userId,
      prdTitle: s.prdTitle,
      startedAt: s.startedAt,
      completedAt: s.completedAt,
      status: s.completedAt
        ? "completed"
        : s.errors.length > 0
        ? "failed"
        : "in_progress",
    }));

    // Filter by status if specified
    if (options.status) {
      return summaries.filter((s) => s.status === options.status);
    }

    // Apply limit if specified
    if (options.limit) {
      return summaries.slice(0, options.limit);
    }

    return summaries;
  }

  /**
   * Clean up old metrics (older than specified days)
   */
  async cleanupOldMetrics(daysOld: number): Promise<void> {
    const cutoffDate = new Date(Date.now() - daysOld * 24 * 60 * 60 * 1000);

    for (const [sessionId, metrics] of this.sessions.entries()) {
      if (metrics.startedAt < cutoffDate) {
        // Delete from memory
        this.sessions.delete(sessionId);

        // Delete from disk
        const filePath = path.join(this.metricsDir, `${sessionId}.json`);
        if (fs.existsSync(filePath)) {
          fs.unlinkSync(filePath);
        }
      }
    }
  }

  /**
   * Close logger and flush to disk
   */
  async close(): Promise<void> {
    // Persist all sessions one final time
    for (const sessionId of this.sessions.keys()) {
      await this.persistMetrics(sessionId);
    }
  }

  // Private methods

  private async persistMetrics(sessionId: string): Promise<void> {
    const metrics = this.sessions.get(sessionId);
    if (!metrics) {
      return;
    }

    const filePath = path.join(this.metricsDir, `${sessionId}.json`);
    const data = JSON.stringify(metrics, null, 2);

    fs.writeFileSync(filePath, data, "utf-8");
  }

  private loadMetricsFromDisk(): void {
    if (!fs.existsSync(this.metricsDir)) {
      return;
    }

    const files = fs.readdirSync(this.metricsDir);

    for (const file of files) {
      if (!file.endsWith(".json")) {
        continue;
      }

      const filePath = path.join(this.metricsDir, file);
      try {
        const data = fs.readFileSync(filePath, "utf-8");
        const metrics = JSON.parse(data, (key, value) => {
          // Parse dates
          if (
            key === "startedAt" ||
            key === "completedAt" ||
            key === "timestamp"
          ) {
            return value ? new Date(value) : undefined;
          }
          return value;
        });

        this.sessions.set(metrics.sessionId, metrics);
      } catch (error) {
        console.error(`Failed to load metrics from ${filePath}:`, error);
      }
    }
  }
}
