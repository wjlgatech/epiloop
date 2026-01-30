/**
 * Workspace Manager - Manages isolated workspaces for autonomous coding sessions
 * Following TDD Iron Law: Tests written first, minimal implementation
 */

import { promises as fs } from "fs";
import * as path from "path";
import { randomUUID } from "crypto";

export interface WorkspaceConfig {
  workspaceRoot: string;
  maxConcurrentSessions?: number;
  maxWorkspaceSizeMB?: number;
  maxExecutionMinutes?: number;
}

export interface Workspace {
  sessionId: string;
  path: string;
  userId: string;
  createdAt: Date;
}

export interface SessionMetadata {
  sessionId: string;
  userId: string;
  description: string;
  createdAt: Date;
  completedAt?: Date;
  status: "active" | "completed" | "failed" | "abandoned";
  error?: string;
  workspacePath: string;
}

export interface WorkspaceUsage {
  sizeMB: number;
  exceededLimit: boolean;
}

/**
 * Manages isolated workspaces for autonomous coding sessions
 */
export class WorkspaceManager {
  private config: WorkspaceConfig;
  private sessions: Map<string, SessionMetadata> = new Map();
  private userSessions: Map<string, Set<string>> = new Map();

  constructor(config: WorkspaceConfig) {
    this.config = {
      maxConcurrentSessions: 3,
      maxWorkspaceSizeMB: 1000, // 1GB default
      maxExecutionMinutes: 120, // 2 hours default
      ...config,
    };
  }

  /**
   * Create isolated workspace for a session
   */
  async createWorkspace(
    userId: string,
    description: string
  ): Promise<Workspace> {
    // Check concurrent session limit
    const userSessionIds = this.userSessions.get(userId) || new Set();
    const activeSessions = Array.from(userSessionIds)
      .map((id) => this.sessions.get(id))
      .filter((s) => s?.status === "active");

    if (activeSessions.length >= this.config.maxConcurrentSessions!) {
      throw new Error(
        `Max concurrent sessions (${this.config.maxConcurrentSessions}) reached for user ${userId}`
      );
    }

    // Generate unique session ID
    const sessionId = randomUUID();

    // Create workspace directory
    const workspacePath = path.join(this.config.workspaceRoot, sessionId);

    try {
      await fs.mkdir(workspacePath, { recursive: true });

      // Create subdirectories
      await fs.mkdir(path.join(workspacePath, "logs"), { recursive: true });
      await fs.mkdir(path.join(workspacePath, "artifacts"), {
        recursive: true,
      });

      // Create session metadata
      const metadata: SessionMetadata = {
        sessionId,
        userId,
        description,
        createdAt: new Date(),
        status: "active",
        workspacePath,
      };

      // Save metadata
      await this.saveSessionMetadata(metadata);

      // Track session
      this.sessions.set(sessionId, metadata);

      if (!this.userSessions.has(userId)) {
        this.userSessions.set(userId, new Set());
      }
      this.userSessions.get(userId)!.add(sessionId);

      return {
        sessionId,
        path: workspacePath,
        userId,
        createdAt: metadata.createdAt,
      };
    } catch (error) {
      throw new Error(
        `Failed to create workspace: ${error instanceof Error ? error.message : String(error)}`
      );
    }
  }

  /**
   * Get session metadata
   */
  async getSessionMetadata(sessionId: string): Promise<SessionMetadata> {
    // Check in-memory cache first
    if (this.sessions.has(sessionId)) {
      return this.sessions.get(sessionId)!;
    }

    // Load from disk
    const workspacePath = path.join(this.config.workspaceRoot, sessionId);
    const metadataPath = path.join(workspacePath, "session.json");

    try {
      const content = await fs.readFile(metadataPath, "utf-8");
      const metadata = JSON.parse(content, (key, value) => {
        if (key === "createdAt" || key === "completedAt") {
          return value ? new Date(value) : undefined;
        }
        return value;
      });

      this.sessions.set(sessionId, metadata);
      return metadata;
    } catch (error) {
      throw new Error(`Session ${sessionId} not found`);
    }
  }

  /**
   * Save session metadata to disk
   */
  async saveSessionMetadata(metadata: SessionMetadata): Promise<void> {
    const metadataPath = path.join(metadata.workspacePath, "session.json");
    await fs.writeFile(metadataPath, JSON.stringify(metadata, null, 2));

    // Update cache
    this.sessions.set(metadata.sessionId, metadata);
  }

  /**
   * Update session status
   */
  async updateSessionStatus(
    sessionId: string,
    status: SessionMetadata["status"]
  ): Promise<void> {
    const metadata = await this.getSessionMetadata(sessionId);
    metadata.status = status;

    if (status === "completed") {
      metadata.completedAt = new Date();
    }

    await this.saveSessionMetadata(metadata);
  }

  /**
   * Mark session as failed
   */
  async markSessionFailed(sessionId: string, error: string): Promise<void> {
    const metadata = await this.getSessionMetadata(sessionId);
    metadata.status = "failed";
    metadata.error = error;
    metadata.completedAt = new Date();

    await this.saveSessionMetadata(metadata);
  }

  /**
   * Get session
   */
  async getSession(sessionId: string): Promise<SessionMetadata> {
    return await this.getSessionMetadata(sessionId);
  }

  /**
   * Get all sessions for a user
   */
  async getUserSessions(userId: string): Promise<SessionMetadata[]> {
    const sessionIds = this.userSessions.get(userId) || new Set();
    const sessions: SessionMetadata[] = [];

    for (const sessionId of sessionIds) {
      try {
        const metadata = await this.getSessionMetadata(sessionId);
        sessions.push(metadata);
      } catch (e) {
        // Session not found, remove from tracking
        this.userSessions.get(userId)?.delete(sessionId);
      }
    }

    return sessions;
  }

  /**
   * Get workspace disk usage
   */
  async getWorkspaceUsage(sessionId: string): Promise<WorkspaceUsage> {
    const metadata = await this.getSessionMetadata(sessionId);
    const size = await this.getDirectorySize(metadata.workspacePath);
    const sizeMB = size / (1024 * 1024);

    return {
      sizeMB,
      exceededLimit: sizeMB > this.config.maxWorkspaceSizeMB!,
    };
  }

  /**
   * Get session elapsed minutes
   */
  async getSessionElapsedMinutes(sessionId: string): Promise<number> {
    const metadata = await this.getSessionMetadata(sessionId);
    const elapsed = Date.now() - metadata.createdAt.getTime();
    return elapsed / (60 * 1000);
  }

  /**
   * Check if session exceeded time limit
   */
  async hasExceededTimeLimit(sessionId: string): Promise<boolean> {
    const elapsed = await this.getSessionElapsedMinutes(sessionId);
    return elapsed > this.config.maxExecutionMinutes!;
  }

  /**
   * Cleanup old completed sessions
   */
  async cleanupOldSessions(daysOld: number): Promise<void> {
    const cutoffDate = new Date(
      Date.now() - daysOld * 24 * 60 * 60 * 1000
    );

    for (const [sessionId, metadata] of this.sessions.entries()) {
      if (
        metadata.status === "completed" &&
        metadata.completedAt &&
        metadata.completedAt < cutoffDate
      ) {
        await this.cleanupSession(sessionId);
      }
    }
  }

  /**
   * Cleanup abandoned sessions
   */
  async cleanupAbandonedSessions(inactiveHours: number): Promise<void> {
    const cutoffDate = new Date(
      Date.now() - inactiveHours * 60 * 60 * 1000
    );

    for (const [sessionId, metadata] of this.sessions.entries()) {
      if (metadata.status === "active" && metadata.createdAt < cutoffDate) {
        await this.markSessionAbandoned(sessionId);
        await this.cleanupSession(sessionId);
      }
    }
  }

  /**
   * Cleanup all sessions for a user
   */
  async cleanupUserSessions(userId: string): Promise<void> {
    const sessionIds = Array.from(this.userSessions.get(userId) || []);

    for (const sessionId of sessionIds) {
      await this.cleanupSession(sessionId);
    }

    this.userSessions.delete(userId);
  }

  /**
   * Cleanup all sessions
   */
  async cleanupAll(): Promise<void> {
    const sessionIds = Array.from(this.sessions.keys());

    for (const sessionId of sessionIds) {
      await this.cleanupSession(sessionId);
    }

    this.sessions.clear();
    this.userSessions.clear();
  }

  // Private methods

  private async cleanupSession(sessionId: string): Promise<void> {
    try {
      const metadata = await this.getSessionMetadata(sessionId);

      // Delete workspace directory
      await fs.rm(metadata.workspacePath, { recursive: true, force: true });

      // Remove from tracking
      this.sessions.delete(sessionId);
      for (const sessionIds of this.userSessions.values()) {
        sessionIds.delete(sessionId);
      }
    } catch (error) {
      // Ignore cleanup errors
    }
  }

  private async markSessionAbandoned(sessionId: string): Promise<void> {
    try {
      const metadata = await this.getSessionMetadata(sessionId);
      metadata.status = "abandoned";
      metadata.completedAt = new Date();
      await this.saveSessionMetadata(metadata);
    } catch (error) {
      // Ignore errors
    }
  }

  private async getDirectorySize(dirPath: string): Promise<number> {
    let size = 0;

    try {
      const files = await fs.readdir(dirPath, { withFileTypes: true });

      for (const file of files) {
        const filePath = path.join(dirPath, file.name);

        if (file.isDirectory()) {
          size += await this.getDirectorySize(filePath);
        } else {
          const stats = await fs.stat(filePath);
          size += stats.size;
        }
      }
    } catch (error) {
      // Ignore errors
    }

    return size;
  }
}
