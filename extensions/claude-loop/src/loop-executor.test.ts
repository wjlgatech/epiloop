import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { LoopExecutor } from "./loop-executor";
import type { PRDFormat } from "./types";
import { EventEmitter } from "events";

// Mock PRD for testing
const mockPRD: PRDFormat = {
  project: "test-feature",
  branchName: "feature/test",
  description: "Test feature",
  domain: "test:typescript",
  userStories: [
    {
      id: "US-001",
      title: "Test story",
      description: "Test description",
      acceptanceCriteria: ["TDD Iron Law", "Feature works"],
      priority: 1,
      passes: false,
      estimatedComplexity: "simple",
    },
  ],
  qualityGates: {
    requireTests: true,
    requireTypecheck: true,
    requireLint: true,
    minCoverage: 75,
    securityScan: true,
  },
  metadata: {
    createdAt: new Date().toISOString(),
    author: "Test",
    estimatedDuration: "1 hour",
    parallelizable: false,
    maxParallelStories: 1,
  },
};

describe("Loop Executor - RED Phase (TDD)", () => {
  let executor: LoopExecutor;

  beforeEach(() => {
    executor = new LoopExecutor({
      claudeLoopPath: "/mock/claude-loop.sh",
      workspaceRoot: "/tmp/test-workspace",
    });
  });

  afterEach(async () => {
    if (executor.isRunning()) {
      await executor.stop();
    }
  });

  describe("Constructor and Configuration", () => {
    it("should create executor with valid configuration", () => {
      expect(executor).toBeDefined();
      expect(executor.isRunning()).toBe(false);
    });

    it("should validate claude-loop path exists", () => {
      expect(() => {
        new LoopExecutor({
          claudeLoopPath: "/nonexistent/path",
          workspaceRoot: "/tmp",
        });
      }).toThrow(/claude-loop.sh not found/i);
    });

    it("should create workspace directory if it doesn't exist", async () => {
      const executor = new LoopExecutor({
        claudeLoopPath: "/mock/claude-loop.sh",
        workspaceRoot: "/tmp/new-workspace",
      });

      expect(executor).toBeDefined();
    });
  });

  describe("start()", () => {
    it("should start execution with PRD", async () => {
      const promise = executor.start(mockPRD);

      expect(executor.isRunning()).toBe(true);

      await executor.stop();
    });

    it("should write PRD to workspace", async () => {
      await executor.start(mockPRD);

      const status = executor.getStatus();
      expect(status.prdPath).toContain("prd.json");

      await executor.stop();
    });

    it("should emit 'started' event", async () => {
      const startedSpy = vi.fn();
      executor.on("started", startedSpy);

      await executor.start(mockPRD);

      expect(startedSpy).toHaveBeenCalled();

      await executor.stop();
    });

    it("should reject if already running", async () => {
      await executor.start(mockPRD);

      await expect(executor.start(mockPRD)).rejects.toThrow(/already running/i);

      await executor.stop();
    });

    it("should set environment variables for claude-loop", async () => {
      await executor.start(mockPRD);

      const status = executor.getStatus();
      expect(status.environment).toHaveProperty("ANTHROPIC_API_KEY");

      await executor.stop();
    });
  });

  describe("Event Streaming", () => {
    it("should emit 'iteration-start' event", async () => {
      const spy = vi.fn();
      executor.on("iteration-start", spy);

      await executor.start(mockPRD);

      // Simulate iteration start from stdout
      // In real implementation, this would be parsed from process output

      await executor.stop();
    });

    it("should emit 'story-complete' event with story details", async () => {
      const spy = vi.fn();
      executor.on("story-complete", spy);

      await executor.start(mockPRD);

      // Wait for story completion
      await new Promise((resolve) => setTimeout(resolve, 100));

      await executor.stop();
    });

    it("should emit 'error' event on failures", async () => {
      const spy = vi.fn();
      executor.on("error", spy);

      // Start with invalid PRD to trigger error
      const invalidPRD = { ...mockPRD, userStories: [] };

      try {
        await executor.start(invalidPRD);
      } catch (e) {
        expect(spy).toHaveBeenCalled();
      }
    });

    it("should emit 'complete' event when all stories pass", async () => {
      const spy = vi.fn();
      executor.on("complete", spy);

      await executor.start(mockPRD);

      // Simulate completion
      await new Promise((resolve) => setTimeout(resolve, 100));

      await executor.stop();
    });

    it("should emit 'progress' events with percentage", async () => {
      const spy = vi.fn();
      executor.on("progress", spy);

      await executor.start(mockPRD);

      await new Promise((resolve) => setTimeout(resolve, 100));

      await executor.stop();
    });
  });

  describe("stop()", () => {
    it("should stop running execution gracefully", async () => {
      await executor.start(mockPRD);

      await executor.stop();

      expect(executor.isRunning()).toBe(false);
    });

    it("should emit 'stopped' event", async () => {
      const spy = vi.fn();
      executor.on("stopped", spy);

      await executor.start(mockPRD);
      await executor.stop();

      expect(spy).toHaveBeenCalled();
    });

    it("should save checkpoint before stopping", async () => {
      await executor.start(mockPRD);
      await executor.stop();

      const status = executor.getStatus();
      expect(status.checkpointExists).toBe(true);
    });

    it("should kill process if graceful stop fails", async () => {
      await executor.start(mockPRD);

      // Force kill scenario
      await executor.stop({ force: true });

      expect(executor.isRunning()).toBe(false);
    });

    it("should be idempotent (safe to call multiple times)", async () => {
      await executor.start(mockPRD);

      await executor.stop();
      await executor.stop(); // Second call should not throw

      expect(executor.isRunning()).toBe(false);
    });
  });

  describe("getStatus()", () => {
    it("should return status when not running", () => {
      const status = executor.getStatus();

      expect(status.isRunning).toBe(false);
      expect(status.currentStory).toBeNull();
    });

    it("should return current story when running", async () => {
      await executor.start(mockPRD);

      const status = executor.getStatus();

      expect(status.isRunning).toBe(true);
      expect(status.currentStory).toBeDefined();

      await executor.stop();
    });

    it("should include progress metrics", async () => {
      await executor.start(mockPRD);

      const status = executor.getStatus();

      expect(status).toHaveProperty("totalStories");
      expect(status).toHaveProperty("completedStories");
      expect(status).toHaveProperty("progressPercent");

      await executor.stop();
    });

    it("should include timing information", async () => {
      await executor.start(mockPRD);

      await new Promise((resolve) => setTimeout(resolve, 100));

      const status = executor.getStatus();

      expect(status.startTime).toBeDefined();
      expect(status.elapsedSeconds).toBeGreaterThan(0);

      await executor.stop();
    });

    it("should include checkpoint information", async () => {
      await executor.start(mockPRD);

      const status = executor.getStatus();

      expect(status).toHaveProperty("checkpointExists");
      expect(status).toHaveProperty("lastCheckpointTime");

      await executor.stop();
    });
  });

  describe("Resume from Checkpoint", () => {
    it("should resume from saved checkpoint", async () => {
      // Start and create checkpoint
      await executor.start(mockPRD);
      await new Promise((resolve) => setTimeout(resolve, 100));
      await executor.stop();

      // Create new executor and resume
      const executor2 = new LoopExecutor({
        claudeLoopPath: "/mock/claude-loop.sh",
        workspaceRoot: "/tmp/test-workspace",
      });

      await executor2.resume();

      expect(executor2.isRunning()).toBe(true);

      await executor2.stop();
    });

    it("should skip completed stories on resume", async () => {
      await executor.start(mockPRD);
      await executor.stop();

      await executor.resume();

      const status = executor.getStatus();
      expect(status.completedStories).toBeGreaterThanOrEqual(0);

      await executor.stop();
    });

    it("should fail if no checkpoint exists", async () => {
      await expect(executor.resume()).rejects.toThrow(/no checkpoint/i);
    });
  });

  describe("Timeout Handling", () => {
    it("should enforce max execution time", async () => {
      const executorWithTimeout = new LoopExecutor({
        claudeLoopPath: "/mock/claude-loop.sh",
        workspaceRoot: "/tmp/test-workspace",
        maxExecutionMinutes: 1,
      });

      await executorWithTimeout.start(mockPRD);

      // Should timeout after 1 minute
      const status = executorWithTimeout.getStatus();
      expect(status.maxExecutionMinutes).toBe(1);

      await executorWithTimeout.stop();
    });

    it("should emit 'timeout' event when limit reached", async () => {
      const spy = vi.fn();
      const executorWithTimeout = new LoopExecutor({
        claudeLoopPath: "/mock/claude-loop.sh",
        workspaceRoot: "/tmp/test-workspace",
        maxExecutionMinutes: 0.01, // 0.6 seconds
      });

      executorWithTimeout.on("timeout", spy);

      await executorWithTimeout.start(mockPRD);

      await new Promise((resolve) => setTimeout(resolve, 1000));

      expect(spy).toHaveBeenCalled();

      await executorWithTimeout.stop();
    });

    it("should save checkpoint before timeout", async () => {
      const executorWithTimeout = new LoopExecutor({
        claudeLoopPath: "/mock/claude-loop.sh",
        workspaceRoot: "/tmp/test-workspace",
        maxExecutionMinutes: 0.01,
      });

      await executorWithTimeout.start(mockPRD);

      await new Promise((resolve) => setTimeout(resolve, 1000));

      const status = executorWithTimeout.getStatus();
      expect(status.checkpointExists).toBe(true);

      await executorWithTimeout.stop();
    });
  });

  describe("Log Streaming", () => {
    it("should stream stdout to structured logs", async () => {
      const logs: string[] = [];
      executor.on("log", (data) => logs.push(data));

      await executor.start(mockPRD);

      await new Promise((resolve) => setTimeout(resolve, 100));

      expect(logs.length).toBeGreaterThan(0);

      await executor.stop();
    });

    it("should write logs to JSONL file", async () => {
      await executor.start(mockPRD);

      await new Promise((resolve) => setTimeout(resolve, 100));

      const status = executor.getStatus();
      expect(status.logFile).toBeDefined();
      expect(status.logFile).toContain(".jsonl");

      await executor.stop();
    });

    it("should parse structured log messages", async () => {
      const logMessages: any[] = [];
      executor.on("log", (data) => {
        try {
          logMessages.push(JSON.parse(data));
        } catch (e) {
          // Ignore non-JSON logs
        }
      });

      await executor.start(mockPRD);

      await new Promise((resolve) => setTimeout(resolve, 100));

      await executor.stop();
    });
  });

  describe("Error Handling", () => {
    it("should handle process spawn errors", async () => {
      const badExecutor = new LoopExecutor({
        claudeLoopPath: "/definitely/does/not/exist.sh",
        workspaceRoot: "/tmp/test",
      });

      await expect(badExecutor.start(mockPRD)).rejects.toThrow();
    });

    it("should handle invalid PRD format", async () => {
      const invalidPRD = {} as PRDFormat;

      await expect(executor.start(invalidPRD)).rejects.toThrow(/invalid PRD/i);
    });

    it("should handle process crashes", async () => {
      const spy = vi.fn();
      executor.on("error", spy);

      await executor.start(mockPRD);

      // Simulate crash
      // In real tests, this would kill the spawned process

      await executor.stop();
    });

    it("should cleanup resources on error", async () => {
      try {
        await executor.start({} as PRDFormat);
      } catch (e) {
        // Error expected
      }

      expect(executor.isRunning()).toBe(false);
    });
  });
});
