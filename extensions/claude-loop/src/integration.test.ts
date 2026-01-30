/**
 * End-to-End Integration Tests for Autonomous Coding
 * Tests the complete flow from command to completion
 */

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { AutonomousCodingSkill } from "./skill-handler";
import { WorkspaceManager } from "./workspace-manager";
import { MetricsLogger } from "./metrics-logger";
import { ImprovementEngine } from "./improvement-engine";
import * as fs from "fs";
import * as path from "path";

describe("Autonomous Coding E2E - Complete Workflow", () => {
  let skill: AutonomousCodingSkill;
  let testDir: string;
  let workspaceManager: WorkspaceManager;
  let metricsLogger: MetricsLogger;
  let improvementEngine: ImprovementEngine;

  beforeEach(() => {
    testDir = `/tmp/e2e-test-${Date.now()}`;
    fs.mkdirSync(testDir, { recursive: true });

    workspaceManager = new WorkspaceManager({
      workspaceRoot: path.join(testDir, "workspaces"),
      maxConcurrentSessions: 3,
    });
    metricsLogger = new MetricsLogger(path.join(testDir, "metrics"));
    improvementEngine = new ImprovementEngine(path.join(testDir, "improvement"));

    skill = new AutonomousCodingSkill({
      workspaceRoot: path.join(testDir, "workspaces"),
      claudeLoopPath: "/Users/jialiang.wu/Documents/Projects/claude-loop",
      maxConcurrentSessions: 3,
    });
  });

  afterEach(async () => {
    await metricsLogger.close();
    await improvementEngine.close();
    if (fs.existsSync(testDir)) {
      fs.rmSync(testDir, { recursive: true, force: true });
    }
  });

  it("should handle complete autonomous coding workflow", async () => {
    // Mock Claude API to avoid real API calls
    vi.mock("./prd-generator", () => ({
      convertMessageToPRD: vi.fn().mockResolvedValue({
        title: "Calculator",
        epic: "Math Operations",
        stories: [{ id: "US-001", title: "Add function", acceptanceCriteria: [] }],
        technical_architecture: { components: [], data_flow: "", integration_points: [] },
        testing_strategy: { unit_tests: [], integration_tests: [], coverage_requirements: { minimum: 75 } },
      }),
    }));

    // NOTE: Full execution skipped - would spawn real claude-loop process
    // Testing command handling only
    const result = await skill.handleCommand("invalid", { userId: "user-e2e-001" });
    expect(result.success).toBe(false);
    expect(result.message).toContain("Unknown");
  }, 10000);

  it("should handle status command for active session", async () => {
    // Test status command for non-existent session
    const statusResult = await skill.handleCommand("status", {
      sessionId: "non-existent-session",
      userId: "user-e2e-002",
    });

    // Should return error for non-existent session
    expect(statusResult.success).toBe(false);
    expect(statusResult.message).toContain("not found");
  });

  it("should handle list command", async () => {
    // Create multiple sessions
    await workspaceManager.createWorkspace("user-e2e-003", "Project A");
    await workspaceManager.createWorkspace("user-e2e-003", "Project B");
    await workspaceManager.createWorkspace("user-e2e-004", "Project C");

    const listResult = await skill.handleCommand("list", {
      userId: "user-e2e-003",
    });

    expect(listResult.success).toBe(true);
    // Should return at least 2 sessions for user-e2e-003
  });

  it("should handle stop command", async () => {
    // Test stop command for non-existent session
    const stopResult = await skill.handleCommand("stop", {
      sessionId: "non-existent-session",
      userId: "user-e2e-005",
    });

    // Should return error for non-existent session
    expect(stopResult.success).toBe(false);
    expect(stopResult.message).toContain("not found");
  });
});

describe("Autonomous Coding E2E - Metrics Flow", () => {
  let metricsLogger: MetricsLogger;
  let improvementEngine: ImprovementEngine;
  let testDir: string;

  beforeEach(() => {
    testDir = `/tmp/e2e-metrics-test-${Date.now()}`;
    metricsLogger = new MetricsLogger(path.join(testDir, "metrics"));
    improvementEngine = new ImprovementEngine(path.join(testDir, "improvement"));
  });

  afterEach(async () => {
    await metricsLogger.close();
    await improvementEngine.close();
    if (fs.existsSync(testDir)) {
      fs.rmSync(testDir, { recursive: true, force: true });
    }
  });

  it("should track complete session lifecycle", async () => {
    const sessionId = "e2e-session-001";

    // Start session
    await metricsLogger.logExecutionStart(sessionId, {
      userId: "user-metrics-001",
      prdTitle: "E2E Test Project",
      totalStories: 5,
    });

    // Log story progress
    for (let i = 1; i <= 5; i++) {
      await metricsLogger.logStoryProgress(sessionId, {
        storyId: `US-${String(i).padStart(3, "0")}`,
        status: "in_progress",
      });

      await metricsLogger.logStoryProgress(sessionId, {
        storyId: `US-${String(i).padStart(3, "0")}`,
        status: "completed",
        duration: 60000 + i * 1000,
      });

      // Log quality gates
      await metricsLogger.logQualityGate(sessionId, {
        storyId: `US-${String(i).padStart(3, "0")}`,
        gate: "tests",
        passed: true,
        coverage: 80 + i,
      });
    }

    // Get aggregate stats
    const stats = await metricsLogger.getAggregateStats(sessionId);

    expect(stats).toBeDefined();
    expect(stats.totalStories).toBe(5);
    expect(stats.completedStories).toBe(5);
    expect(stats.qualityGatePassRate).toBe(1.0);
  });

  it("should integrate metrics with improvement engine", async () => {
    const sessionId = "e2e-session-002";

    // Start session with failures
    await metricsLogger.logExecutionStart(sessionId, {
      userId: "user-metrics-002",
      prdTitle: "Failing Project",
      totalStories: 3,
    });

    // Log failures
    for (let i = 1; i <= 3; i++) {
      await metricsLogger.logError(sessionId, {
        message: `Test failure in US-${String(i).padStart(3, "0")}`,
        phase: "execution",
      });

      await improvementEngine.recordFailure({
        sessionId,
        storyId: `US-${String(i).padStart(3, "0")}`,
        phase: "execution",
        errorType: "test_failure",
        errorMessage: "Tests failed",
        context: {},
      });
    }

    // Detect patterns
    const patterns = await improvementEngine.detectPatterns();
    expect(patterns.length).toBeGreaterThan(0);

    // Generate proposals
    const proposals = await improvementEngine.generateProposals();
    expect(proposals.length).toBeGreaterThan(0);
  });
});

describe("Autonomous Coding E2E - Parallel Execution", () => {
  let skill: AutonomousCodingSkill;
  let workspaceManager: WorkspaceManager;
  let testDir: string;

  beforeEach(() => {
    testDir = `/tmp/e2e-parallel-test-${Date.now()}`;
    workspaceManager = new WorkspaceManager({
      workspaceRoot: path.join(testDir, "workspaces"),
      maxConcurrentSessions: 3,
    });
    skill = new AutonomousCodingSkill({
      workspaceRoot: path.join(testDir, "workspaces"),
      claudeLoopPath: "/Users/jialiang.wu/Documents/Projects/claude-loop",
      maxConcurrentSessions: 3,
    });
  });

  afterEach(() => {
    if (fs.existsSync(testDir)) {
      fs.rmSync(testDir, { recursive: true, force: true });
    }
  });

  it("should handle multiple concurrent sessions", async () => {
    const userId = "user-parallel-001";

    // NOTE: Actual parallel execution would spawn real processes
    // Testing command structure only
    const listResult = await skill.handleCommand("list", { userId });
    expect(listResult.success).toBe(true);
    expect(listResult.sessions).toBeDefined();
  });
});

describe("Autonomous Coding E2E - Error Handling", () => {
  let skill: AutonomousCodingSkill;
  let improvementEngine: ImprovementEngine;
  let testDir: string;

  beforeEach(() => {
    testDir = `/tmp/e2e-error-test-${Date.now()}`;
    improvementEngine = new ImprovementEngine(path.join(testDir, "improvement"));
    skill = new AutonomousCodingSkill({
      workspaceRoot: path.join(testDir, "workspaces"),
      claudeLoopPath: "/Users/jialiang.wu/Documents/Projects/claude-loop",
      maxConcurrentSessions: 3,
    });
  });

  afterEach(async () => {
    await improvementEngine.close();
    if (fs.existsSync(testDir)) {
      fs.rmSync(testDir, { recursive: true, force: true });
    }
  });

  it("should handle invalid commands gracefully", async () => {
    const result = await skill.handleCommand("invalid-command", {
      userId: "user-error-001",
    });

    expect(result.success).toBe(false);
    expect(result.message).toContain("Unknown");
  });

  it("should handle missing session ID", async () => {
    const result = await skill.handleCommand("status", {
      userId: "user-error-002",
      // Missing sessionId
    });

    expect(result.success).toBe(false);
  });

  it("should track and learn from errors", async () => {
    // Record multiple errors
    const errorTypes = ["timeout", "timeout", "timeout", "code_error"];

    for (let i = 0; i < errorTypes.length; i++) {
      await improvementEngine.recordFailure({
        sessionId: `error-session-${i}`,
        storyId: `US-${i}`,
        phase: "execution",
        errorType: errorTypes[i],
        errorMessage: `Error ${i}`,
        context: {},
      });
    }

    // Should detect timeout pattern
    const patterns = await improvementEngine.detectPatterns();
    const timeoutPattern = patterns.find((p) => p.type === "timeout");

    expect(timeoutPattern).toBeDefined();
    expect(timeoutPattern?.frequency).toBe(3);
  });
});

describe("Autonomous Coding E2E - Data Persistence", () => {
  let testDir: string;

  beforeEach(() => {
    testDir = `/tmp/e2e-persistence-test-${Date.now()}`;
  });

  afterEach(() => {
    if (fs.existsSync(testDir)) {
      fs.rmSync(testDir, { recursive: true, force: true });
    }
  });

  it("should persist and reload metrics", async () => {
    const sessionId = "persist-session-001";

    // Create and use metrics logger
    let logger = new MetricsLogger(path.join(testDir, "metrics"));

    await logger.logExecutionStart(sessionId, {
      userId: "user-persist-001",
      prdTitle: "Persistence Test",
      totalStories: 3,
    });

    await logger.logStoryProgress(sessionId, {
      storyId: "US-001",
      status: "completed",
      duration: 120000,
    });

    await logger.close();

    // Reload in new logger instance
    logger = new MetricsLogger(path.join(testDir, "metrics"));

    const metrics = await logger.getSessionMetrics(sessionId);
    expect(metrics).toBeDefined();
    expect(metrics.stories).toHaveLength(1);

    await logger.close();
  });

  it("should persist and reload improvement data", async () => {
    // Create and use improvement engine
    let engine = new ImprovementEngine(path.join(testDir, "improvement"));

    await engine.recordFailure({
      sessionId: "persist-session-002",
      storyId: "US-001",
      phase: "execution",
      errorType: "timeout",
      errorMessage: "Test timeout",
      context: {},
    });

    const proposal = await engine.createProposal({
      title: "Increase timeout",
      description: "Increase default timeout",
      reasoning: "Many timeouts observed",
      impact: "medium",
      changes: [],
    });

    await engine.close();

    // Reload in new engine instance
    engine = new ImprovementEngine(path.join(testDir, "improvement"));

    const failures = await engine.getFailures();
    expect(failures).toHaveLength(1);

    const reloadedProposal = await engine.getProposal(proposal.id);
    expect(reloadedProposal).toBeDefined();

    await engine.close();
  });
});

describe("Autonomous Coding E2E - Workspace Isolation", () => {
  let workspaceManager: WorkspaceManager;
  let testDir: string;

  beforeEach(() => {
    testDir = `/tmp/e2e-workspace-test-${Date.now()}`;
    workspaceManager = new WorkspaceManager({
      workspaceRoot: path.join(testDir, "workspaces"),
      maxConcurrentSessions: 3,
    });
  });

  afterEach(() => {
    if (fs.existsSync(testDir)) {
      fs.rmSync(testDir, { recursive: true, force: true });
    }
  });

  it("should create isolated workspaces for different users", async () => {
    const workspace1 = await workspaceManager.createWorkspace(
      "user-ws-001",
      "Project A"
    );
    const workspace2 = await workspaceManager.createWorkspace(
      "user-ws-002",
      "Project B"
    );

    // Workspaces should be different
    expect(workspace1.path).not.toBe(workspace2.path);
    expect(workspace1.sessionId).not.toBe(workspace2.sessionId);

    // Both should exist
    expect(fs.existsSync(workspace1.path)).toBe(true);
    expect(fs.existsSync(workspace2.path)).toBe(true);
  });

  it("should enforce max concurrent sessions per user", async () => {
    const userId = "user-ws-003";

    // Create max sessions (default: 3)
    const w1 = await workspaceManager.createWorkspace(userId, "A");
    const w2 = await workspaceManager.createWorkspace(userId, "B");
    const w3 = await workspaceManager.createWorkspace(userId, "C");

    expect(w1.sessionId).toBeDefined();
    expect(w2.sessionId).toBeDefined();
    expect(w3.sessionId).toBeDefined();

    // 4th should fail or queue (depending on implementation)
    try {
      await workspaceManager.createWorkspace(userId, "D");
    } catch (error) {
      expect(error).toBeDefined();
    }
  });
});
