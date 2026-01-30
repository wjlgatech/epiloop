/**
 * Configuration management for claude-loop extension
 */

import * as fs from "fs";
import * as path from "path";
import * as os from "os";
import { fileURLToPath } from "url";
import { dirname } from "path";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

export interface AutonomousCodingConfig {
  qualityGates: {
    requireTests: boolean;
    requireTypecheck: boolean;
    requireLint: boolean;
    minCoverage: number;
    securityScan: boolean;
  };
  execution: {
    maxConcurrent: number;
    timeout: number;
    maxMemoryPerTask: number;
    maxDiskPerTask: number;
  };
  workspace: {
    cleanupDays: number;
    maxConcurrentPerUser: number;
  };
  reporting: {
    verbosity: "minimal" | "normal" | "detailed";
    batchDelay: number;
  };
  improvement: {
    autoGenerateProposals: boolean;
    minPatternFrequency: number;
    reportPeriod: "daily" | "weekly" | "monthly";
  };
  claudeLoop: {
    path: string;
    workspaceRoot: string;
  };
}

/**
 * Load configuration with defaults and user overrides
 */
export function loadConfig(): AutonomousCodingConfig {
  // Load defaults
  const defaultsPath = path.join(__dirname, "../config/defaults.json");
  const defaults: AutonomousCodingConfig = JSON.parse(
    fs.readFileSync(defaultsPath, "utf-8")
  );

  // Try to load user config
  const userConfigPath = path.join(
    os.homedir(),
    ".epiloop/config/autonomous-coding.json"
  );

  let userConfig: Partial<AutonomousCodingConfig> = {};
  if (fs.existsSync(userConfigPath)) {
    try {
      userConfig = JSON.parse(fs.readFileSync(userConfigPath, "utf-8"));
    } catch (error) {
      console.warn(`Failed to load user config from ${userConfigPath}:`, error);
    }
  }

  // Merge configs (deep merge)
  const config = {
    qualityGates: {
      ...defaults.qualityGates,
      ...userConfig.qualityGates,
    },
    execution: {
      ...defaults.execution,
      ...userConfig.execution,
    },
    workspace: {
      ...defaults.workspace,
      ...userConfig.workspace,
    },
    reporting: {
      ...defaults.reporting,
      ...userConfig.reporting,
    },
    improvement: {
      ...defaults.improvement,
      ...userConfig.improvement,
    },
    claudeLoop: {
      ...defaults.claudeLoop,
      ...userConfig.claudeLoop,
    },
  };

  // Expand ~ in paths
  config.claudeLoop.workspaceRoot = config.claudeLoop.workspaceRoot.replace(
    /^~/,
    os.homedir()
  );

  // Validate config
  validateConfig(config);

  return config;
}

/**
 * Validate configuration values
 */
function validateConfig(config: AutonomousCodingConfig): void {
  // Validate quality gates
  if (config.qualityGates.minCoverage < 0 || config.qualityGates.minCoverage > 100) {
    throw new Error("minCoverage must be between 0 and 100");
  }

  // Validate execution
  if (config.execution.maxConcurrent < 1) {
    throw new Error("maxConcurrent must be at least 1");
  }

  if (config.execution.timeout < 60000) {
    throw new Error("timeout must be at least 60000ms (1 minute)");
  }

  // Validate workspace
  if (config.workspace.cleanupDays < 1) {
    throw new Error("cleanupDays must be at least 1");
  }

  if (config.workspace.maxConcurrentPerUser < 1) {
    throw new Error("maxConcurrentPerUser must be at least 1");
  }

  // Validate claude-loop path exists
  if (!fs.existsSync(config.claudeLoop.path)) {
    throw new Error(`Claude-loop path does not exist: ${config.claudeLoop.path}`);
  }
}

/**
 * Get default config (useful for testing)
 */
export function getDefaultConfig(): AutonomousCodingConfig {
  const defaultsPath = path.join(__dirname, "../config/defaults.json");
  return JSON.parse(fs.readFileSync(defaultsPath, "utf-8"));
}
