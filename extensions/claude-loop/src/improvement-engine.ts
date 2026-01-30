/**
 * Improvement Engine - Self-learning feedback loop
 * Learns from failures and successes to generate improvement proposals
 */

import * as fs from "fs";
import * as path from "path";

export interface FailureRecord {
  id?: string;
  sessionId: string;
  storyId: string;
  phase: string;
  errorType: string;
  errorMessage: string;
  context: Record<string, any>;
  timestamp?: Date;
}

export interface SuccessRecord {
  id?: string;
  sessionId: string;
  storyId: string;
  duration: number;
  context: Record<string, any>;
  timestamp?: Date;
}

export interface FailurePattern {
  type: string;
  frequency: number;
  examples: FailureRecord[];
}

export interface ImprovementProposal {
  id: string;
  title: string;
  description: string;
  reasoning: string;
  impact: "low" | "medium" | "high";
  changes: Array<{
    file: string;
    description: string;
  }>;
  status: "pending" | "approved" | "rejected" | "applied";
  createdAt: Date;
  reviewedAt?: Date;
  rejectionReason?: string;
}

export interface ProposalInput {
  title: string;
  description: string;
  reasoning: string;
  impact: "low" | "medium" | "high";
  changes: Array<{
    file: string;
    description: string;
  }>;
}

export interface Report {
  totalAttempts: number;
  successRate: number;
  failuresByType: Record<string, number>;
  topFailures: FailurePattern[];
  proposalsGenerated: number;
  proposalsApplied: number;
}

export interface CalibrationData {
  successRate: number;
  dataPoints: Array<{
    date: Date;
    rate: number;
  }>;
}

export interface GetFailuresOptions {
  sessionId?: string;
  errorType?: string;
  limit?: number;
}

export interface GetSuccessesOptions {
  sessionId?: string;
  limit?: number;
}

export interface ListProposalsOptions {
  status?: "pending" | "approved" | "rejected" | "applied";
  limit?: number;
}

export interface CalibrationOptions {
  days?: number;
}

/**
 * Engine for self-improvement through failure analysis and proposal generation
 */
export class ImprovementEngine {
  private dataDir: string;
  private failures: FailureRecord[] = [];
  private successes: SuccessRecord[] = [];
  private proposals: ImprovementProposal[] = [];
  private recordCounter = 0;
  private proposalCounter = 0;

  constructor(dataDir: string) {
    this.dataDir = dataDir;

    // Create data directory if it doesn't exist
    if (!fs.existsSync(dataDir)) {
      fs.mkdirSync(dataDir, { recursive: true });
    }

    // Load existing data
    this.loadData();
  }

  /**
   * Record a failure for learning
   */
  async recordFailure(failure: FailureRecord): Promise<void> {
    const record: FailureRecord = {
      ...failure,
      id: `failure-${++this.recordCounter}`,
      timestamp: failure.timestamp || new Date(),
    };

    this.failures.push(record);
    await this.persistData();
  }

  /**
   * Record a success for calibration
   */
  async recordSuccess(success: SuccessRecord): Promise<void> {
    const record: SuccessRecord = {
      ...success,
      id: `success-${++this.recordCounter}`,
      timestamp: success.timestamp || new Date(),
    };

    this.successes.push(record);
    await this.persistData();
  }

  /**
   * Get failures with optional filtering
   */
  async getFailures(options: GetFailuresOptions = {}): Promise<FailureRecord[]> {
    let filtered = [...this.failures];

    if (options.sessionId) {
      filtered = filtered.filter((f) => f.sessionId === options.sessionId);
    }

    if (options.errorType) {
      filtered = filtered.filter((f) => f.errorType === options.errorType);
    }

    if (options.limit) {
      filtered = filtered.slice(0, options.limit);
    }

    return filtered;
  }

  /**
   * Get successes with optional filtering
   */
  async getSuccesses(
    options: GetSuccessesOptions = {}
  ): Promise<SuccessRecord[]> {
    let filtered = [...this.successes];

    if (options.sessionId) {
      filtered = filtered.filter((s) => s.sessionId === options.sessionId);
    }

    if (options.limit) {
      filtered = filtered.slice(0, options.limit);
    }

    return filtered;
  }

  /**
   * Calculate overall success rate
   */
  async getSuccessRate(): Promise<number> {
    const total = this.failures.length + this.successes.length;
    if (total === 0) return 0;
    return this.successes.length / total;
  }

  /**
   * Detect patterns in failures
   */
  async detectPatterns(): Promise<FailurePattern[]> {
    const patternMap = new Map<string, FailureRecord[]>();

    // Group by error type
    for (const failure of this.failures) {
      const existing = patternMap.get(failure.errorType) || [];
      existing.push(failure);
      patternMap.set(failure.errorType, existing);
    }

    // Convert to patterns
    const patterns: FailurePattern[] = [];
    for (const [type, failures] of patternMap.entries()) {
      patterns.push({
        type,
        frequency: failures.length,
        examples: failures.slice(0, 3), // Top 3 examples
      });
    }

    // Sort by frequency
    patterns.sort((a, b) => b.frequency - a.frequency);

    return patterns;
  }

  /**
   * Generate improvement proposals based on patterns
   */
  async generateProposals(): Promise<ImprovementProposal[]> {
    const patterns = await this.detectPatterns();
    const newProposals: ImprovementProposal[] = [];

    for (const pattern of patterns) {
      // Only generate proposal if pattern occurs frequently
      if (pattern.frequency >= 3) {
        const proposal = await this.createProposal({
          title: `Address ${pattern.type} failures`,
          description: `Pattern detected: ${pattern.frequency} occurrences of ${pattern.type}`,
          reasoning: `This failure type is occurring frequently and should be addressed`,
          impact: pattern.frequency >= 5 ? "high" : "medium",
          changes: [
            {
              file: "TBD",
              description: `Implement fix for ${pattern.type}`,
            },
          ],
        });

        newProposals.push(proposal);
      }
    }

    return newProposals;
  }

  /**
   * Create a new improvement proposal
   */
  async createProposal(input: ProposalInput): Promise<ImprovementProposal> {
    const proposal: ImprovementProposal = {
      id: `proposal-${++this.proposalCounter}`,
      ...input,
      status: "pending",
      createdAt: new Date(),
    };

    this.proposals.push(proposal);
    await this.persistData();

    return proposal;
  }

  /**
   * Get a specific proposal
   */
  async getProposal(id: string): Promise<ImprovementProposal | undefined> {
    return this.proposals.find((p) => p.id === id);
  }

  /**
   * Approve a proposal
   */
  async approveProposal(id: string): Promise<void> {
    const proposal = this.proposals.find((p) => p.id === id);
    if (!proposal) {
      throw new Error(`Proposal ${id} not found`);
    }

    proposal.status = "approved";
    proposal.reviewedAt = new Date();
    await this.persistData();
  }

  /**
   * Reject a proposal
   */
  async rejectProposal(id: string, reason: string): Promise<void> {
    const proposal = this.proposals.find((p) => p.id === id);
    if (!proposal) {
      throw new Error(`Proposal ${id} not found`);
    }

    proposal.status = "rejected";
    proposal.reviewedAt = new Date();
    proposal.rejectionReason = reason;
    await this.persistData();
  }

  /**
   * List proposals with optional filtering
   */
  async listProposals(
    options: ListProposalsOptions = {}
  ): Promise<ImprovementProposal[]> {
    let filtered = [...this.proposals];

    if (options.status) {
      filtered = filtered.filter((p) => p.status === options.status);
    }

    if (options.limit) {
      filtered = filtered.slice(0, options.limit);
    }

    return filtered;
  }

  /**
   * Generate a report
   */
  async generateReport(period: "daily" | "weekly" | "monthly"): Promise<Report> {
    const total = this.failures.length + this.successes.length;
    const successRate = total > 0 ? this.successes.length / total : 0;

    // Count failures by type
    const failuresByType: Record<string, number> = {};
    for (const failure of this.failures) {
      failuresByType[failure.errorType] =
        (failuresByType[failure.errorType] || 0) + 1;
    }

    // Get top patterns
    const patterns = await this.detectPatterns();
    const topFailures = patterns.slice(0, 5);

    // Count proposals
    const proposalsGenerated = this.proposals.length;
    const proposalsApplied = this.proposals.filter(
      (p) => p.status === "applied"
    ).length;

    return {
      totalAttempts: total,
      successRate,
      failuresByType,
      topFailures,
      proposalsGenerated,
      proposalsApplied,
    };
  }

  /**
   * Get calibration data over time
   */
  async getCalibration(
    options: CalibrationOptions = {}
  ): Promise<CalibrationData> {
    const days = options.days || 30;
    const cutoff = new Date(Date.now() - days * 24 * 60 * 60 * 1000);

    // Filter to recent data
    const recentFailures = this.failures.filter(
      (f) => f.timestamp && f.timestamp >= cutoff
    );
    const recentSuccesses = this.successes.filter(
      (s) => s.timestamp && s.timestamp >= cutoff
    );

    const total = recentFailures.length + recentSuccesses.length;
    const successRate = total > 0 ? recentSuccesses.length / total : 0;

    // Group by day
    const dayMap = new Map<string, { successes: number; total: number }>();

    for (const success of recentSuccesses) {
      if (!success.timestamp) continue;
      const day = success.timestamp.toISOString().split("T")[0];
      const entry = dayMap.get(day) || { successes: 0, total: 0 };
      entry.successes++;
      entry.total++;
      dayMap.set(day, entry);
    }

    for (const failure of recentFailures) {
      if (!failure.timestamp) continue;
      const day = failure.timestamp.toISOString().split("T")[0];
      const entry = dayMap.get(day) || { successes: 0, total: 0 };
      entry.total++;
      dayMap.set(day, entry);
    }

    // Convert to data points
    const dataPoints = Array.from(dayMap.entries())
      .map(([day, data]) => ({
        date: new Date(day),
        rate: data.total > 0 ? data.successes / data.total : 0,
      }))
      .sort((a, b) => a.date.getTime() - b.date.getTime());

    return {
      successRate,
      dataPoints,
    };
  }

  /**
   * Close engine and flush data
   */
  async close(): Promise<void> {
    await this.persistData();
  }

  // Private methods

  private async persistData(): Promise<void> {
    const data = {
      failures: this.failures,
      successes: this.successes,
      proposals: this.proposals,
      recordCounter: this.recordCounter,
      proposalCounter: this.proposalCounter,
    };

    const filePath = path.join(this.dataDir, "improvement-data.json");
    fs.writeFileSync(filePath, JSON.stringify(data, null, 2), "utf-8");
  }

  private loadData(): void {
    const filePath = path.join(this.dataDir, "improvement-data.json");

    if (!fs.existsSync(filePath)) {
      return;
    }

    try {
      const content = fs.readFileSync(filePath, "utf-8");
      const data = JSON.parse(content, (key, value) => {
        // Parse dates
        if (key === "timestamp" || key === "createdAt" || key === "reviewedAt") {
          return value ? new Date(value) : undefined;
        }
        return value;
      });

      this.failures = data.failures || [];
      this.successes = data.successes || [];
      this.proposals = data.proposals || [];
      this.recordCounter = data.recordCounter || 0;
      this.proposalCounter = data.proposalCounter || 0;
    } catch (error) {
      console.error("Failed to load improvement data:", error);
    }
  }
}
