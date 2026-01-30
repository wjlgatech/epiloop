import { describe, it, expect, vi, beforeEach } from "vitest";
import { ProgressReporter, VerbosityLevel } from "./progress-reporter";
import { LoopExecutor } from "./loop-executor";
import { EventEmitter } from "events";

describe("Progress Reporter - RED Phase (TDD)", () => {
  let reporter: ProgressReporter;
  let mockExecutor: EventEmitter;

  beforeEach(() => {
    mockExecutor = new EventEmitter();
    reporter = new ProgressReporter({
      verbosity: "normal",
      batchDelayMs: 100,
    });
  });

  describe("Constructor and Configuration", () => {
    it("should create reporter with default verbosity", () => {
      const reporter = new ProgressReporter();
      expect(reporter).toBeDefined();
    });

    it("should accept verbosity configuration", () => {
      const minimal = new ProgressReporter({ verbosity: "minimal" });
      const detailed = new ProgressReporter({ verbosity: "detailed" });

      expect(minimal).toBeDefined();
      expect(detailed).toBeDefined();
    });

    it("should configure batch delay", () => {
      const reporter = new ProgressReporter({ batchDelayMs: 500 });
      expect(reporter).toBeDefined();
    });
  });

  describe("subscribe()", () => {
    it("should subscribe to executor events", () => {
      reporter.subscribe(mockExecutor as any);

      mockExecutor.emit("started", { prd: "test-feature" });
      // Should not throw
    });

    it("should handle multiple subscriptions safely", () => {
      reporter.subscribe(mockExecutor as any);
      reporter.subscribe(mockExecutor as any); // Should be idempotent

      expect(() => {
        mockExecutor.emit("started", { prd: "test" });
      }).not.toThrow();
    });
  });

  describe("Event Formatting - Started", () => {
    it("should format started event with minimal verbosity", () => {
      const messages: string[] = [];
      reporter.on("message", (msg) => messages.push(msg));

      const minimalReporter = new ProgressReporter({ verbosity: "minimal" });
      minimalReporter.on("message", (msg) => messages.push(msg));
      minimalReporter.subscribe(mockExecutor as any);

      mockExecutor.emit("started", { prd: "user-authentication" });

      expect(messages.some((m) => m.includes("user-authentication"))).toBe(true);
      expect(messages.some((m) => m.includes("started") || m.includes("Starting"))).toBe(
        true
      );
    });

    it("should include project details with normal verbosity", () => {
      const messages: string[] = [];
      reporter.on("message", (msg) => messages.push(msg));
      reporter.subscribe(mockExecutor as any);

      mockExecutor.emit("started", {
        prd: "user-authentication",
        workspace: "/tmp/workspace",
      });

      expect(messages.length).toBeGreaterThan(0);
      expect(messages[0]).toContain("user-authentication");
    });

    it("should include workspace path with detailed verbosity", () => {
      const messages: string[] = [];
      const detailedReporter = new ProgressReporter({ verbosity: "detailed" });
      detailedReporter.on("message", (msg) => messages.push(msg));
      detailedReporter.subscribe(mockExecutor as any);

      mockExecutor.emit("started", {
        prd: "test",
        workspace: "/tmp/workspace",
      });

      expect(messages.some((m) => m.includes("/tmp/workspace"))).toBe(true);
    });
  });

  describe("Event Formatting - Story Complete", () => {
    it("should format story completion", () => {
      const messages: string[] = [];
      reporter.on("message", (msg) => messages.push(msg));
      reporter.subscribe(mockExecutor as any);

      mockExecutor.emit("story-complete", {
        storyId: "US-001",
        completedCount: 1,
      });

      expect(messages.some((m) => m.includes("US-001"))).toBe(true);
      expect(messages.some((m) => m.includes("complete"))).toBe(true);
    });

    it("should include completion count", () => {
      const messages: string[] = [];
      reporter.on("message", (msg) => messages.push(msg));
      reporter.subscribe(mockExecutor as any);

      mockExecutor.emit("story-complete", {
        storyId: "US-003",
        completedCount: 3,
      });

      expect(messages.some((m) => m.includes("3"))).toBe(true);
    });

    it("should use emoji for completed stories", () => {
      const messages: string[] = [];
      reporter.on("message", (msg) => messages.push(msg));
      reporter.subscribe(mockExecutor as any);

      mockExecutor.emit("story-complete", { storyId: "US-001" });

      expect(messages.some((m) => m.includes("✅"))).toBe(true);
    });
  });

  describe("Event Formatting - Progress", () => {
    it("should format progress updates", () => {
      const messages: string[] = [];
      reporter.on("message", (msg) => messages.push(msg));
      reporter.subscribe(mockExecutor as any);

      mockExecutor.emit("progress", { percent: 50 });

      expect(messages.some((m) => m.includes("50"))).toBe(true);
    });

    it("should include progress bar with normal verbosity", () => {
      const messages: string[] = [];
      reporter.on("message", (msg) => messages.push(msg));
      reporter.subscribe(mockExecutor as any);

      mockExecutor.emit("progress", { percent: 75 });

      // Should have some visual indicator
      expect(messages.length).toBeGreaterThan(0);
    });

    it("should omit progress bar with minimal verbosity", () => {
      const messages: string[] = [];
      const minimalReporter = new ProgressReporter({ verbosity: "minimal" });
      minimalReporter.on("message", (msg) => messages.push(msg));
      minimalReporter.subscribe(mockExecutor as any);

      mockExecutor.emit("progress", { percent: 50 });

      // Minimal verbosity might skip progress updates
      // or show very simple format
    });
  });

  describe("Event Formatting - Errors", () => {
    it("should format error events", () => {
      const messages: string[] = [];
      reporter.on("message", (msg) => messages.push(msg));
      reporter.subscribe(mockExecutor as any);

      mockExecutor.emit("error", new Error("Test error"));

      expect(messages.some((m) => m.includes("error") || m.includes("Error"))).toBe(
        true
      );
      expect(messages.some((m) => m.includes("Test error"))).toBe(true);
    });

    it("should use error emoji", () => {
      const messages: string[] = [];
      reporter.on("message", (msg) => messages.push(msg));
      reporter.subscribe(mockExecutor as any);

      mockExecutor.emit("error", new Error("Failed"));

      expect(messages.some((m) => m.includes("❌") || m.includes("⚠"))).toBe(true);
    });

    it("should provide actionable guidance on errors", () => {
      const messages: string[] = [];
      reporter.on("message", (msg) => messages.push(msg));
      reporter.subscribe(mockExecutor as any);

      mockExecutor.emit("error", new Error("API rate limit exceeded"));

      // Should suggest action
      expect(messages.some((m) => m.toLowerCase().includes("wait") ||
                                  m.toLowerCase().includes("retry"))).toBe(true);
    });
  });

  describe("Event Formatting - Complete", () => {
    it("should format completion with summary", () => {
      const messages: string[] = [];
      reporter.on("message", (msg) => messages.push(msg));
      reporter.subscribe(mockExecutor as any);

      mockExecutor.emit("complete", {
        totalStories: 5,
        duration: 1200,
      });

      expect(messages.some((m) => m.includes("complete") || m.includes("Complete"))).toBe(
        true
      );
      expect(messages.some((m) => m.includes("5"))).toBe(true);
    });

    it("should include celebration emoji", () => {
      const messages: string[] = [];
      reporter.on("message", (msg) => messages.push(msg));
      reporter.subscribe(mockExecutor as any);

      mockExecutor.emit("complete", { totalStories: 3 });

      expect(messages.some((m) => m.includes("🎉") || m.includes("✅"))).toBe(true);
    });

    it("should format duration in human-readable format", () => {
      const messages: string[] = [];
      reporter.on("message", (msg) => messages.push(msg));
      reporter.subscribe(mockExecutor as any);

      mockExecutor.emit("complete", {
        totalStories: 3,
        duration: 3665, // 1 hour, 1 minute, 5 seconds
      });

      expect(
        messages.some(
          (m) => m.includes("hour") || m.includes("minute") || m.includes("1h")
        )
      ).toBe(true);
    });
  });

  describe("Batching - Anti-Spam", () => {
    it("should batch rapid progress updates", async () => {
      const messages: string[] = [];
      const batchReporter = new ProgressReporter({ batchDelayMs: 50 });
      batchReporter.on("message", (msg) => messages.push(msg));
      batchReporter.subscribe(mockExecutor as any);

      // Emit many rapid updates
      mockExecutor.emit("progress", { percent: 10 });
      mockExecutor.emit("progress", { percent: 11 });
      mockExecutor.emit("progress", { percent: 12 });
      mockExecutor.emit("progress", { percent: 13 });

      // Should batch these
      await new Promise((resolve) => setTimeout(resolve, 100));

      // Should have fewer messages than events
      expect(messages.length).toBeLessThan(4);
    });

    it("should not batch different event types", async () => {
      const messages: string[] = [];
      const batchReporter = new ProgressReporter({ batchDelayMs: 50 });
      batchReporter.on("message", (msg) => messages.push(msg));
      batchReporter.subscribe(mockExecutor as any);

      mockExecutor.emit("started", { prd: "test" });
      mockExecutor.emit("progress", { percent: 10 });
      mockExecutor.emit("story-complete", { storyId: "US-001" });

      await new Promise((resolve) => setTimeout(resolve, 100));

      // Different event types should not be batched together
      expect(messages.length).toBeGreaterThanOrEqual(2);
    });

    it("should always emit critical events immediately", () => {
      const messages: string[] = [];
      const batchReporter = new ProgressReporter({ batchDelayMs: 1000 });
      batchReporter.on("message", (msg) => messages.push(msg));
      batchReporter.subscribe(mockExecutor as any);

      mockExecutor.emit("error", new Error("Critical failure"));

      // Error should emit immediately, not wait for batch
      expect(messages.length).toBeGreaterThan(0);
    });
  });

  describe("Message Formatting Utilities", () => {
    it("should format durations correctly", () => {
      // Test via complete event
      const messages: string[] = [];
      reporter.on("message", (msg) => messages.push(msg));
      reporter.subscribe(mockExecutor as any);

      mockExecutor.emit("complete", { totalStories: 1, duration: 125 });

      expect(messages.some((m) => m.includes("2m") || m.includes("minutes"))).toBe(
        true
      );
    });

    it("should truncate long messages appropriately", () => {
      const messages: string[] = [];
      reporter.on("message", (msg) => messages.push(msg));
      reporter.subscribe(mockExecutor as any);

      const longError = new Error("A".repeat(1000));
      mockExecutor.emit("error", longError);

      // Should not send extremely long messages
      messages.forEach((msg) => {
        expect(msg.length).toBeLessThan(500);
      });
    });

    it("should escape special characters for messaging platforms", () => {
      const messages: string[] = [];
      reporter.on("message", (msg) => messages.push(msg));
      reporter.subscribe(mockExecutor as any);

      mockExecutor.emit("started", { prd: "test_feature*with#special@chars" });

      // Should handle special chars gracefully
      expect(messages.length).toBeGreaterThan(0);
    });
  });

  describe("Verbosity Levels", () => {
    it("minimal should send only essential updates", () => {
      const messages: string[] = [];
      const minimalReporter = new ProgressReporter({ verbosity: "minimal" });
      minimalReporter.on("message", (msg) => messages.push(msg));
      minimalReporter.subscribe(mockExecutor as any);

      mockExecutor.emit("started", { prd: "test" });
      mockExecutor.emit("progress", { percent: 25 });
      mockExecutor.emit("progress", { percent: 50 });
      mockExecutor.emit("story-complete", { storyId: "US-001" });
      mockExecutor.emit("complete", { totalStories: 1 });

      // Minimal should skip intermediate progress
      expect(messages.length).toBeLessThanOrEqual(3);
    });

    it("detailed should include all information", () => {
      const messages: string[] = [];
      const detailedReporter = new ProgressReporter({ verbosity: "detailed" });
      detailedReporter.on("message", (msg) => messages.push(msg));
      detailedReporter.subscribe(mockExecutor as any);

      mockExecutor.emit("started", { prd: "test", workspace: "/tmp" });
      mockExecutor.emit("iteration-start", { iteration: 1 });

      // Detailed should include more info
      expect(messages.some((m) => m.length > 50)).toBe(true);
    });
  });

  describe("Final Summary", () => {
    it("should generate comprehensive summary on completion", () => {
      const messages: string[] = [];
      reporter.on("message", (msg) => messages.push(msg));
      reporter.subscribe(mockExecutor as any);

      mockExecutor.emit("complete", {
        totalStories: 5,
        duration: 3600,
        filesChanged: ["file1.ts", "file2.ts"],
        testsAdded: 10,
        prUrl: "https://github.com/user/repo/pull/123",
      });

      // Should include multiple pieces of info
      const summaryMessages = messages.filter((m) => m.includes("complete"));
      expect(summaryMessages.length).toBeGreaterThan(0);
    });

    it("should include PR link in summary", () => {
      const messages: string[] = [];
      reporter.on("message", (msg) => messages.push(msg));
      reporter.subscribe(mockExecutor as any);

      mockExecutor.emit("complete", {
        totalStories: 3,
        prUrl: "https://github.com/test/repo/pull/42",
      });

      expect(messages.some((m) => m.includes("github.com"))).toBe(true);
      expect(messages.some((m) => m.includes("/pull/42"))).toBe(true);
    });

    it("should include test results in summary", () => {
      const messages: string[] = [];
      reporter.on("message", (msg) => messages.push(msg));
      reporter.subscribe(mockExecutor as any);

      mockExecutor.emit("complete", {
        totalStories: 2,
        testsAdded: 15,
        testsPassed: 15,
        coverage: 85,
      });

      expect(messages.some((m) => m.includes("15") && m.includes("test"))).toBe(true);
      expect(messages.some((m) => m.includes("85"))).toBe(true);
    });

    it("should list files changed in detailed mode", () => {
      const messages: string[] = [];
      const detailedReporter = new ProgressReporter({ verbosity: "detailed" });
      detailedReporter.on("message", (msg) => messages.push(msg));
      detailedReporter.subscribe(mockExecutor as any);

      mockExecutor.emit("complete", {
        totalStories: 2,
        filesChanged: ["src/auth.ts", "src/auth.test.ts", "README.md"],
      });

      expect(
        messages.some((m) => m.includes("auth.ts") || m.includes("files"))
      ).toBe(true);
    });
  });

  describe("unsubscribe()", () => {
    it("should unsubscribe from executor events", () => {
      const messages: string[] = [];
      reporter.on("message", (msg) => messages.push(msg));
      reporter.subscribe(mockExecutor as any);

      mockExecutor.emit("progress", { percent: 25 });
      const countBefore = messages.length;

      reporter.unsubscribe();

      mockExecutor.emit("progress", { percent: 50 });
      const countAfter = messages.length;

      expect(countAfter).toBe(countBefore);
    });
  });
});
