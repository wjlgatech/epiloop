import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { WorkspaceManager } from "./workspace-manager";
import { promises as fs } from "fs";
import * as path from "path";
import { tmpdir } from "os";

describe("Workspace Manager - RED Phase (TDD)", () => {
  let manager: WorkspaceManager;
  let testRoot: string;

  beforeEach(async () => {
    testRoot = path.join(tmpdir(), `test-workspaces-${Date.now()}`);
    manager = new WorkspaceManager({
      workspaceRoot: testRoot,
      maxConcurrentSessions: 3,
    });
  });

  afterEach(async () => {
    await manager.cleanupAll();
    try {
      await fs.rm(testRoot, { recursive: true, force: true });
    } catch (e) {
      // Ignore cleanup errors
    }
  });

  describe("createWorkspace", () => {
    it("should create isolated workspace directory", async () => {
      const workspace = await manager.createWorkspace("user1", "test-session");

      expect(workspace.path).toBeDefined();
      expect(workspace.sessionId).toBeDefined();

      const stats = await fs.stat(workspace.path);
      expect(stats.isDirectory()).toBe(true);
    });

    it("should create workspace with required subdirectories", async () => {
      const workspace = await manager.createWorkspace("user1", "test");

      const logsDir = path.join(workspace.path, "logs");
      const artifactsDir = path.join(workspace.path, "artifacts");

      expect(await fs.stat(logsDir)).toBeDefined();
      expect(await fs.stat(artifactsDir)).toBeDefined();
    });

    it("should track session metadata", async () => {
      const workspace = await manager.createWorkspace("user1", "test");

      const metadata = await manager.getSessionMetadata(workspace.sessionId);

      expect(metadata.userId).toBe("user1");
      expect(metadata.sessionId).toBe(workspace.sessionId);
      expect(metadata.createdAt).toBeDefined();
      expect(metadata.status).toBe("active");
    });

    it("should enforce max concurrent sessions per user", async () => {
      await manager.createWorkspace("user1", "session1");
      await manager.createWorkspace("user1", "session2");
      await manager.createWorkspace("user1", "session3");

      await expect(
        manager.createWorkspace("user1", "session4")
      ).rejects.toThrow(/max concurrent sessions/i);
    });

    it("should allow different users to have concurrent sessions", async () => {
      await manager.createWorkspace("user1", "session1");
      await manager.createWorkspace("user2", "session2");
      await manager.createWorkspace("user3", "session3");

      const user1Sessions = await manager.getUserSessions("user1");
      const user2Sessions = await manager.getUserSessions("user2");

      expect(user1Sessions.length).toBe(1);
      expect(user2Sessions.length).toBe(1);
    });

    it("should generate unique session IDs", async () => {
      const ws1 = await manager.createWorkspace("user1", "test");
      const ws2 = await manager.createWorkspace("user1", "test");

      expect(ws1.sessionId).not.toBe(ws2.sessionId);
    });
  });

  describe("Resource Limits", () => {
    it("should enforce disk space limits", async () => {
      const limitedManager = new WorkspaceManager({
        workspaceRoot: testRoot,
        maxWorkspaceSizeMB: 1, // 1MB limit
      });

      const workspace = await limitedManager.createWorkspace("user1", "test");

      // Try to write 2MB file
      const largefile = path.join(workspace.path, "large.bin");
      const twoMB = Buffer.alloc(2 * 1024 * 1024);

      await fs.writeFile(largefile, twoMB);

      const usage = await limitedManager.getWorkspaceUsage(workspace.sessionId);
      expect(usage.sizeMB).toBeGreaterThan(1);
      expect(usage.exceededLimit).toBe(true);
    });

    it("should enforce execution time limits", async () => {
      const workspace = await manager.createWorkspace("user1", "test");

      const elapsed = await manager.getSessionElapsedMinutes(
        workspace.sessionId
      );

      expect(elapsed).toBeGreaterThanOrEqual(0);
      expect(elapsed).toBeLessThan(1);
    });

    it("should check if session exceeded time limit", async () => {
      const limitedManager = new WorkspaceManager({
        workspaceRoot: testRoot,
        maxExecutionMinutes: 0.01, // Very short for testing
      });

      const workspace = await limitedManager.createWorkspace("user1", "test");

      // Wait a bit
      await new Promise((resolve) => setTimeout(resolve, 100));

      const exceeded = await limitedManager.hasExceededTimeLimit(
        workspace.sessionId
      );

      expect(exceeded).toBe(true);
    });
  });

  describe("Session Management", () => {
    it("should list all active sessions for user", async () => {
      await manager.createWorkspace("user1", "session1");
      await manager.createWorkspace("user1", "session2");
      await manager.createWorkspace("user2", "session3");

      const user1Sessions = await manager.getUserSessions("user1");

      expect(user1Sessions.length).toBe(2);
      expect(user1Sessions.every((s) => s.userId === "user1")).toBe(true);
    });

    it("should update session status", async () => {
      const workspace = await manager.createWorkspace("user1", "test");

      await manager.updateSessionStatus(workspace.sessionId, "completed");

      const metadata = await manager.getSessionMetadata(workspace.sessionId);
      expect(metadata.status).toBe("completed");
    });

    it("should mark session as failed", async () => {
      const workspace = await manager.createWorkspace("user1", "test");

      await manager.markSessionFailed(workspace.sessionId, "Test error");

      const metadata = await manager.getSessionMetadata(workspace.sessionId);
      expect(metadata.status).toBe("failed");
      expect(metadata.error).toBe("Test error");
    });

    it("should get session by ID", async () => {
      const workspace = await manager.createWorkspace("user1", "test");

      const session = await manager.getSession(workspace.sessionId);

      expect(session).toBeDefined();
      expect(session.sessionId).toBe(workspace.sessionId);
      expect(session.userId).toBe("user1");
    });
  });

  describe("Cleanup Policies", () => {
    it("should cleanup completed sessions older than threshold", async () => {
      const workspace = await manager.createWorkspace("user1", "test");
      await manager.updateSessionStatus(workspace.sessionId, "completed");

      // Manually set old timestamp
      const metadata = await manager.getSessionMetadata(workspace.sessionId);
      metadata.completedAt = new Date(Date.now() - 8 * 24 * 60 * 60 * 1000); // 8 days ago
      await manager.saveSessionMetadata(metadata);

      await manager.cleanupOldSessions(7); // Cleanup older than 7 days

      await expect(
        manager.getSessionMetadata(workspace.sessionId)
      ).rejects.toThrow(/not found/i);
    });

    it("should cleanup abandoned sessions", async () => {
      const workspace = await manager.createWorkspace("user1", "test");

      // Set old timestamp for active session (abandoned)
      const metadata = await manager.getSessionMetadata(workspace.sessionId);
      metadata.createdAt = new Date(Date.now() - 2 * 24 * 60 * 60 * 1000); // 2 days ago
      await manager.saveSessionMetadata(metadata);

      await manager.cleanupAbandonedSessions(24); // Cleanup if inactive for 24 hours

      await expect(
        manager.getSessionMetadata(workspace.sessionId)
      ).rejects.toThrow(/not found/i);
    });

    it("should not cleanup active recent sessions", async () => {
      const workspace = await manager.createWorkspace("user1", "test");

      await manager.cleanupOldSessions(7);

      const metadata = await manager.getSessionMetadata(workspace.sessionId);
      expect(metadata).toBeDefined();
    });

    it("should cleanup all sessions for user", async () => {
      await manager.createWorkspace("user1", "session1");
      await manager.createWorkspace("user1", "session2");
      await manager.createWorkspace("user2", "session3");

      await manager.cleanupUserSessions("user1");

      const user1Sessions = await manager.getUserSessions("user1");
      const user2Sessions = await manager.getUserSessions("user2");

      expect(user1Sessions.length).toBe(0);
      expect(user2Sessions.length).toBe(1);
    });
  });

  describe("Workspace Isolation", () => {
    it("should create isolated workspaces for concurrent sessions", async () => {
      const ws1 = await manager.createWorkspace("user1", "session1");
      const ws2 = await manager.createWorkspace("user1", "session2");

      expect(ws1.path).not.toBe(ws2.path);

      // Write to ws1
      await fs.writeFile(path.join(ws1.path, "test.txt"), "ws1 content");

      // Check ws2 doesn't have it
      await expect(
        fs.readFile(path.join(ws2.path, "test.txt"))
      ).rejects.toThrow();
    });

    it("should include session metadata file in workspace", async () => {
      const workspace = await manager.createWorkspace("user1", "test");

      const metadataPath = path.join(workspace.path, "session.json");
      const content = await fs.readFile(metadataPath, "utf-8");
      const metadata = JSON.parse(content);

      expect(metadata.sessionId).toBe(workspace.sessionId);
      expect(metadata.userId).toBe("user1");
    });
  });

  describe("Error Handling", () => {
    it("should handle workspace creation failures gracefully", async () => {
      const badManager = new WorkspaceManager({
        workspaceRoot: "/invalid/nonexistent/path",
      });

      await expect(
        badManager.createWorkspace("user1", "test")
      ).rejects.toThrow();
    });

    it("should throw on invalid session ID", async () => {
      await expect(
        manager.getSessionMetadata("invalid-session-id")
      ).rejects.toThrow(/not found/i);
    });

    it("should handle cleanup errors gracefully", async () => {
      // Should not throw even if nothing to cleanup
      await expect(manager.cleanupOldSessions(7)).resolves.not.toThrow();
    });
  });
});
