/**
 * Tests for ImprovementEngine
 * Following RG-TDD methodology - Reality-Grounded Test Driven Development
 */

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { ImprovementEngine } from "./improvement-engine";
import * as fs from "fs";

describe("ImprovementEngine - Foundation Layer", () => {
  let engine: ImprovementEngine;
  let testDir: string;

  beforeEach(() => {
    testDir = `/tmp/improvement-test-${Date.now()}`;
    engine = new ImprovementEngine(testDir);
  });

  afterEach(async () => {
    await engine.close();
    if (fs.existsSync(testDir)) {
      fs.rmSync(testDir, { recursive: true, force: true });
    }
  });

  it("should create engine instance", () => {
    expect(engine).toBeDefined();
  });

  it("should record a failure", async () => {
    await engine.recordFailure({
      sessionId: "session-001",
      storyId: "US-001",
      phase: "execution",
      errorType: "code_error",
      errorMessage: "Syntax error in generated code",
      context: {
        prdSnippet: "Create a function to parse JSON",
        codeAttempt: "function parse() { return JSON.parse(; }",
      },
    });

    const failures = await engine.getFailures({ sessionId: "session-001" });
    expect(failures).toHaveLength(1);
    expect(failures[0].storyId).toBe("US-001");
  });

  it("should record a success", async () => {
    await engine.recordSuccess({
      sessionId: "session-002",
      storyId: "US-002",
      duration: 120000,
      context: {
        prdSnippet: "Create a simple test",
        approach: "TDD with vitest",
      },
    });

    const successes = await engine.getSuccesses({ sessionId: "session-002" });
    expect(successes).toHaveLength(1);
    expect(successes[0].storyId).toBe("US-002");
  });

  it("should calculate success rate", async () => {
    await engine.recordSuccess({
      sessionId: "test",
      storyId: "US-001",
      duration: 100000,
      context: {},
    });

    await engine.recordSuccess({
      sessionId: "test",
      storyId: "US-002",
      duration: 120000,
      context: {},
    });

    await engine.recordFailure({
      sessionId: "test",
      storyId: "US-003",
      phase: "execution",
      errorType: "timeout",
      errorMessage: "Execution timeout",
      context: {},
    });

    const rate = await engine.getSuccessRate();
    expect(rate).toBeCloseTo(0.67, 2); // 2 successes out of 3 total
  });
});

describe("ImprovementEngine - Challenge Layer", () => {
  let engine: ImprovementEngine;
  let testDir: string;

  beforeEach(() => {
    testDir = `/tmp/improvement-test-${Date.now()}`;
    engine = new ImprovementEngine(testDir);
  });

  afterEach(async () => {
    await engine.close();
    if (fs.existsSync(testDir)) {
      fs.rmSync(testDir, { recursive: true, force: true });
    }
  });

  it("should detect failure patterns", async () => {
    // Record multiple failures of same type
    for (let i = 1; i <= 5; i++) {
      await engine.recordFailure({
        sessionId: `session-${i}`,
        storyId: `US-${i}`,
        phase: "execution",
        errorType: "timeout",
        errorMessage: `Execution timeout after ${3600000}ms`,
        context: { totalStories: 10 },
      });
    }

    const patterns = await engine.detectPatterns();
    expect(patterns).toHaveLength(1);
    expect(patterns[0].type).toBe("timeout");
    expect(patterns[0].frequency).toBe(5);
  });

  it("should generate improvement proposals", async () => {
    // Record failures that suggest an improvement
    for (let i = 1; i <= 3; i++) {
      await engine.recordFailure({
        sessionId: `session-${i}`,
        storyId: `US-${i}`,
        phase: "quality_gate",
        errorType: "test_failure",
        errorMessage: "Tests failed: expected 3 to equal 4",
        context: {},
      });
    }

    const proposals = await engine.generateProposals();
    expect(proposals.length).toBeGreaterThan(0);
    expect(proposals[0].status).toBe("pending");
  });

  it("should approve and apply improvement", async () => {
    // Create a proposal
    const proposal = await engine.createProposal({
      title: "Increase test timeout",
      description: "Increase default test timeout from 5s to 10s",
      reasoning: "Many tests are timing out at 5s",
      impact: "medium",
      changes: [
        {
          file: "vitest.config.ts",
          description: "Update testTimeout to 10000",
        },
      ],
    });

    expect(proposal.id).toBeDefined();
    expect(proposal.status).toBe("pending");

    // Approve proposal
    await engine.approveProposal(proposal.id);

    const updated = await engine.getProposal(proposal.id);
    expect(updated?.status).toBe("approved");
  });

  it("should reject improvement proposal", async () => {
    const proposal = await engine.createProposal({
      title: "Test proposal",
      description: "Test",
      reasoning: "Test",
      impact: "low",
      changes: [],
    });

    await engine.rejectProposal(proposal.id, "Not needed");

    const updated = await engine.getProposal(proposal.id);
    expect(updated?.status).toBe("rejected");
    expect(updated?.rejectionReason).toBe("Not needed");
  });

  it("should list pending proposals", async () => {
    await engine.createProposal({
      title: "Proposal 1",
      description: "Test",
      reasoning: "Test",
      impact: "low",
      changes: [],
    });

    await engine.createProposal({
      title: "Proposal 2",
      description: "Test",
      reasoning: "Test",
      impact: "high",
      changes: [],
    });

    const pending = await engine.listProposals({ status: "pending" });
    expect(pending).toHaveLength(2);
  });
});

describe("ImprovementEngine - Reality Layer", () => {
  let engine: ImprovementEngine;
  let testDir: string;

  beforeEach(() => {
    testDir = `/tmp/improvement-test-${Date.now()}`;
    engine = new ImprovementEngine(testDir);
  });

  afterEach(async () => {
    await engine.close();
    if (fs.existsSync(testDir)) {
      fs.rmSync(testDir, { recursive: true, force: true });
    }
  });

  it("should persist and reload data", async () => {
    await engine.recordFailure({
      sessionId: "session-001",
      storyId: "US-001",
      phase: "execution",
      errorType: "code_error",
      errorMessage: "Test error",
      context: {},
    });

    await engine.createProposal({
      title: "Test improvement",
      description: "Test",
      reasoning: "Test",
      impact: "low",
      changes: [],
    });

    // Close and reopen
    await engine.close();

    const newEngine = new ImprovementEngine(testDir);
    const failures = await newEngine.getFailures();
    const proposals = await newEngine.listProposals();

    expect(failures).toHaveLength(1);
    expect(proposals).toHaveLength(1);

    await newEngine.close();
  });

  it("should generate monthly report", async () => {
    // Record some data
    await engine.recordSuccess({
      sessionId: "s1",
      storyId: "US-001",
      duration: 100000,
      context: {},
    });

    await engine.recordFailure({
      sessionId: "s2",
      storyId: "US-002",
      phase: "execution",
      errorType: "timeout",
      errorMessage: "Timeout",
      context: {},
    });

    const report = await engine.generateReport("monthly");
    expect(report).toBeDefined();
    expect(report.totalAttempts).toBe(2);
    expect(report.successRate).toBeCloseTo(0.5, 2);
    expect(report.failuresByType).toHaveProperty("timeout");
  });

  it("should track calibration over time", async () => {
    const now = Date.now();

    // Record successes and failures over time
    for (let day = 0; day < 30; day++) {
      const timestamp = new Date(now - day * 24 * 60 * 60 * 1000);

      await engine.recordSuccess({
        sessionId: `s-${day}`,
        storyId: `US-${day}`,
        duration: 100000,
        context: {},
        timestamp,
      });

      if (day % 3 === 0) {
        await engine.recordFailure({
          sessionId: `f-${day}`,
          storyId: `US-F-${day}`,
          phase: "execution",
          errorType: "code_error",
          errorMessage: "Error",
          context: {},
          timestamp,
        });
      }
    }

    const calibration = await engine.getCalibration({ days: 30 });
    expect(calibration).toBeDefined();
    expect(calibration.successRate).toBeGreaterThan(0);
    expect(calibration.dataPoints.length).toBeGreaterThan(0);
  });

  it("should handle large volumes of data", async () => {
    // Record 100 failures
    const startTime = Date.now();

    for (let i = 1; i <= 100; i++) {
      await engine.recordFailure({
        sessionId: `session-${i}`,
        storyId: `US-${i}`,
        phase: "execution",
        errorType: i % 2 === 0 ? "timeout" : "code_error",
        errorMessage: `Error ${i}`,
        context: {},
      });
    }

    const endTime = Date.now();
    const duration = endTime - startTime;

    // Should complete in reasonable time (< 5 seconds)
    expect(duration).toBeLessThan(5000);

    const failures = await engine.getFailures();
    expect(failures).toHaveLength(100);

    const patterns = await engine.detectPatterns();
    expect(patterns.length).toBeGreaterThan(0);
  });
});
