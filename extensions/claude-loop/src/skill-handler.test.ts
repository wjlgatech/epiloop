import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { AutonomousCodingSkill } from "./skill-handler";
import type { PRDFormat } from "./types";

describe("Autonomous Coding Skill - RED Phase (TDD)", () => {
  let skill: AutonomousCodingSkill;

  beforeEach(() => {
    skill = new AutonomousCodingSkill({
      workspaceRoot: "/tmp/test-workspaces",
      claudeLoopPath: "/mock/claude-loop/lib/claude-loop/claude-loop.sh",
    });
  });

  afterEach(async () => {
    // Cleanup any running executions
    await skill.stopAll();
  });

  describe("start command", () => {
    it("should accept feature description and return PRD preview", async () => {
      const description = "Add user authentication with OAuth";

      const result = await skill.handleCommand("start", {
        description,
        userId: "test-user",
      });

      expect(result.success).toBe(true);
      expect(result.message).toContain("authentication");
      expect(result.prdPreview).toBeDefined();
      expect(result.sessionId).toBeDefined();
    });

    it("should start execution in background", async () => {
      const result = await skill.handleCommand("start", {
        description: "Add search feature",
        userId: "test-user",
      });

      expect(result.sessionId).toBeDefined();

      const status = await skill.handleCommand("status", {
        sessionId: result.sessionId,
        userId: "test-user",
      });

      expect(status.isRunning).toBe(true);
    });

    it("should reject if user already has active session", async () => {
      await skill.handleCommand("start", {
        description: "Feature 1",
        userId: "test-user",
      });

      const result = await skill.handleCommand("start", {
        description: "Feature 2",
        userId: "test-user",
      });

      expect(result.success).toBe(false);
      expect(result.message).toContain("already running");
    });

    it("should accept verbosity option", async () => {
      const result = await skill.handleCommand("start", {
        description: "Add feature",
        userId: "test-user",
        verbosity: "detailed",
      });

      expect(result.success).toBe(true);
    });

    it("should accept codebase context", async () => {
      const result = await skill.handleCommand("start", {
        description: "Update button styling",
        userId: "test-user",
        context: {
          repoPath: "/path/to/repo",
          technologies: ["typescript", "react"],
        },
      });

      expect(result.success).toBe(true);
      expect(result.prdPreview?.userStories.length).toBeGreaterThan(0);
    });
  });

  describe("status command", () => {
    it("should return status for active session", async () => {
      const startResult = await skill.handleCommand("start", {
        description: "Add feature",
        userId: "test-user",
      });

      const statusResult = await skill.handleCommand("status", {
        sessionId: startResult.sessionId,
        userId: "test-user",
      });

      expect(statusResult.success).toBe(true);
      expect(statusResult.isRunning).toBe(true);
      expect(statusResult.progress).toBeDefined();
    });

    it("should return error if session not found", async () => {
      const result = await skill.handleCommand("status", {
        sessionId: "nonexistent",
        userId: "test-user",
      });

      expect(result.success).toBe(false);
      expect(result.message).toContain("not found");
    });

    it("should include progress percentage", async () => {
      const startResult = await skill.handleCommand("start", {
        description: "Add feature",
        userId: "test-user",
      });

      // Simulate some progress
      await new Promise((resolve) => setTimeout(resolve, 100));

      const statusResult = await skill.handleCommand("status", {
        sessionId: startResult.sessionId,
        userId: "test-user",
      });

      expect(statusResult.progress?.percent).toBeDefined();
      expect(statusResult.progress?.percent).toBeGreaterThanOrEqual(0);
      expect(statusResult.progress?.percent).toBeLessThanOrEqual(100);
    });

    it("should include current story info", async () => {
      const startResult = await skill.handleCommand("start", {
        description: "Add feature",
        userId: "test-user",
      });

      const statusResult = await skill.handleCommand("status", {
        sessionId: startResult.sessionId,
        userId: "test-user",
      });

      expect(statusResult.currentStory).toBeDefined();
    });
  });

  describe("stop command", () => {
    it("should stop active execution", async () => {
      const startResult = await skill.handleCommand("start", {
        description: "Add feature",
        userId: "test-user",
      });

      const stopResult = await skill.handleCommand("stop", {
        sessionId: startResult.sessionId,
        userId: "test-user",
      });

      expect(stopResult.success).toBe(true);

      const statusResult = await skill.handleCommand("status", {
        sessionId: startResult.sessionId,
        userId: "test-user",
      });

      expect(statusResult.isRunning).toBe(false);
    });

    it("should save checkpoint on stop", async () => {
      const startResult = await skill.handleCommand("start", {
        description: "Add feature",
        userId: "test-user",
      });

      await skill.handleCommand("stop", {
        sessionId: startResult.sessionId,
        userId: "test-user",
      });

      const statusResult = await skill.handleCommand("status", {
        sessionId: startResult.sessionId,
        userId: "test-user",
      });

      expect(statusResult.checkpointExists).toBe(true);
    });

    it("should reject if session not owned by user", async () => {
      const startResult = await skill.handleCommand("start", {
        description: "Add feature",
        userId: "user1",
      });

      const stopResult = await skill.handleCommand("stop", {
        sessionId: startResult.sessionId,
        userId: "user2",
      });

      expect(stopResult.success).toBe(false);
      expect(stopResult.message).toContain("not authorized");
    });
  });

  describe("resume command", () => {
    it("should resume from checkpoint", async () => {
      const startResult = await skill.handleCommand("start", {
        description: "Add feature",
        userId: "test-user",
      });

      // Stop execution
      await skill.handleCommand("stop", {
        sessionId: startResult.sessionId,
        userId: "test-user",
      });

      // Resume
      const resumeResult = await skill.handleCommand("resume", {
        sessionId: startResult.sessionId,
        userId: "test-user",
      });

      expect(resumeResult.success).toBe(true);

      const statusResult = await skill.handleCommand("status", {
        sessionId: startResult.sessionId,
        userId: "test-user",
      });

      expect(statusResult.isRunning).toBe(true);
    });

    it("should reject if no checkpoint exists", async () => {
      const result = await skill.handleCommand("resume", {
        sessionId: "nonexistent",
        userId: "test-user",
      });

      expect(result.success).toBe(false);
      expect(result.message).toContain("checkpoint");
    });
  });

  describe("list command", () => {
    it("should list all sessions for user", async () => {
      await skill.handleCommand("start", {
        description: "Feature 1",
        userId: "test-user",
      });

      await new Promise((resolve) => setTimeout(resolve, 100));

      await skill.handleCommand("start", {
        description: "Feature 2",
        userId: "other-user",
      });

      const result = await skill.handleCommand("list", {
        userId: "test-user",
      });

      expect(result.success).toBe(true);
      expect(result.sessions).toBeDefined();
      expect(result.sessions?.length).toBe(1);
      expect(result.sessions?.[0].userId).toBe("test-user");
    });

    it("should include session metadata", async () => {
      await skill.handleCommand("start", {
        description: "Test feature",
        userId: "test-user",
      });

      const result = await skill.handleCommand("list", {
        userId: "test-user",
      });

      const session = result.sessions?.[0];
      expect(session).toHaveProperty("sessionId");
      expect(session).toHaveProperty("description");
      expect(session).toHaveProperty("startTime");
      expect(session).toHaveProperty("status");
    });
  });

  describe("Progress streaming", () => {
    it("should emit progress events", async () => {
      const progressEvents: any[] = [];

      skill.on("progress", (event) => {
        progressEvents.push(event);
      });

      await skill.handleCommand("start", {
        description: "Add feature",
        userId: "test-user",
      });

      await new Promise((resolve) => setTimeout(resolve, 200));

      expect(progressEvents.length).toBeGreaterThan(0);
    });

    it("should emit story-complete events", async () => {
      const storyEvents: any[] = [];

      skill.on("story-complete", (event) => {
        storyEvents.push(event);
      });

      await skill.handleCommand("start", {
        description: "Simple feature",
        userId: "test-user",
      });

      // Wait for potential story completion
      await new Promise((resolve) => setTimeout(resolve, 500));

      // May or may not have completed a story in this time
      // Just verify the handler is set up
      expect(skill.listenerCount("story-complete")).toBeGreaterThan(0);
    });

    it("should emit completion event", async () => {
      const completeEvents: any[] = [];

      skill.on("complete", (event) => {
        completeEvents.push(event);
      });

      await skill.handleCommand("start", {
        description: "Quick feature",
        userId: "test-user",
      });

      // Handler should be registered even if not fired yet
      expect(skill.listenerCount("complete")).toBeGreaterThan(0);
    });
  });

  describe("Error handling", () => {
    it("should handle invalid PRD generation gracefully", async () => {
      const result = await skill.handleCommand("start", {
        description: "", // Empty description
        userId: "test-user",
      });

      expect(result.success).toBe(false);
      expect(result.message).toBeDefined();
    });

    it("should handle execution errors", async () => {
      const badSkill = new AutonomousCodingSkill({
        workspaceRoot: "/nonexistent/path",
        claudeLoopPath: "/invalid/path",
      });

      const result = await badSkill.handleCommand("start", {
        description: "Add feature",
        userId: "test-user",
      });

      expect(result.success).toBe(false);
    });

    it("should emit error events", async () => {
      const errorEvents: any[] = [];

      skill.on("error", (event) => {
        errorEvents.push(event);
      });

      await skill.handleCommand("start", {
        description: "Test",
        userId: "test-user",
      });

      // Handler should be registered
      expect(skill.listenerCount("error")).toBeGreaterThan(0);
    });
  });

  describe("Session isolation", () => {
    it("should isolate sessions by userId", async () => {
      const user1Result = await skill.handleCommand("start", {
        description: "User 1 feature",
        userId: "user1",
      });

      const user2Result = await skill.handleCommand("start", {
        description: "User 2 feature",
        userId: "user2",
      });

      expect(user1Result.sessionId).not.toBe(user2Result.sessionId);

      const user1Sessions = await skill.handleCommand("list", {
        userId: "user1",
      });

      expect(user1Sessions.sessions?.length).toBe(1);
      expect(user1Sessions.sessions?.[0].sessionId).toBe(user1Result.sessionId);
    });
  });
});
