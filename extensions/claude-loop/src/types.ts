/**
 * Type definitions for claude-loop integration
 */

export interface UserStory {
  id: string;
  title: string;
  description: string;
  acceptanceCriteria: string[];
  priority: number;
  passes: boolean;
  estimatedComplexity: "simple" | "medium" | "complex";
  suggestedModel?: "sonnet" | "haiku" | "opus";
  fileScope?: string[];
  dependencies?: string[];
  notes?: string;
}

export interface PRDFormat {
  project: string;
  branchName: string;
  description: string;
  domain: string;
  userStories: UserStory[];
  qualityGates: {
    requireTests: boolean;
    requireTypecheck: boolean;
    requireLint: boolean;
    minCoverage: number;
    securityScan: boolean;
  };
  metadata: {
    createdAt: string;
    author: string;
    estimatedDuration: string;
    parallelizable: boolean;
    maxParallelStories: number;
  };
}

export interface CodebaseContext {
  repoPath: string;
  technologies?: string[];
  existingFiles?: string[];
  testingFramework?: string;
  lintConfig?: string;
}
