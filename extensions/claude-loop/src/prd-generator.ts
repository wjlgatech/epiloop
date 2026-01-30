/**
 * PRD Generator - Converts natural language feature requests to structured PRDs
 * Following TDD Iron Law: Tests written first, minimal implementation
 */

import Anthropic from "@anthropic-ai/sdk";
import type { PRDFormat, CodebaseContext, UserStory } from "./types.js";

const TDD_IRON_LAW_CRITERION =
  "Tests written FIRST (RED phase), then minimal implementation (GREEN phase), following TDD Iron Law";

/**
 * Convert a natural language message to a structured PRD format
 * @param message - User's feature request in natural language
 * @param context - Optional codebase context for better PRD generation
 * @returns Promise<PRDFormat> - Structured PRD ready for claude-loop execution
 */
export async function convertMessageToPRD(
  message: string,
  context?: CodebaseContext
): Promise<PRDFormat> {
  // Initialize Anthropic client
  const client = new Anthropic({
    apiKey: process.env.ANTHROPIC_API_KEY || "",
  });

  // Build context prompt
  const contextPrompt = context
    ? `

Codebase Context:
- Repository: ${context.repoPath}
- Technologies: ${context.technologies?.join(", ") || "unknown"}
- Testing Framework: ${context.testingFramework || "unknown"}
- Linting: ${context.lintConfig || "unknown"}
- Existing Files: ${context.existingFiles?.slice(0, 10).join(", ") || "none provided"}
`
    : "";

  const systemPrompt = `You are a PRD generator that converts natural language feature requests into structured Product Requirement Documents (PRDs) for autonomous coding agents.

Your job is to analyze the user's feature request and generate a complete PRD in JSON format with:
1. User stories broken down from the feature request
2. Acceptance criteria for each story (ALWAYS include TDD Iron Law as first criterion)
3. Priority ordering
4. Complexity estimates (simple/medium/complex)
5. Suggested AI models (haiku for simple, sonnet for medium/complex, opus for very complex)
6. File scope predictions
7. Dependencies between stories
8. Quality gates configuration
9. Domain classification

CRITICAL RULES:
- EVERY user story MUST have "${TDD_IRON_LAW_CRITERION}" as the FIRST acceptance criterion
- Break complex requests into 2-8 user stories
- Simple requests can be 1 story
- Assign realistic priorities (1 = highest)
- Mark all stories as "passes": false initially
- Create valid git branch names (lowercase, hyphens, no spaces)
- Detect domain from feature description (e.g., "api:typescript:auth", "frontend:react:ui")
- Set dependencies between stories when one depends on another

Return ONLY valid JSON matching this schema, no markdown formatting:
{
  "project": "string (kebab-case project name)",
  "branchName": "feature/project-name",
  "description": "string (clear description of the feature)",
  "domain": "string (e.g., 'api:typescript:auth')",
  "userStories": [
    {
      "id": "US-001",
      "title": "string",
      "description": "string",
      "acceptanceCriteria": ["${TDD_IRON_LAW_CRITERION}", "...other criteria"],
      "priority": 1,
      "passes": false,
      "estimatedComplexity": "simple|medium|complex",
      "suggestedModel": "haiku|sonnet|opus",
      "fileScope": ["file paths"],
      "dependencies": ["US-XXX"]
    }
  ],
  "qualityGates": {
    "requireTests": true,
    "requireTypecheck": true,
    "requireLint": true,
    "minCoverage": 75,
    "securityScan": true
  },
  "metadata": {
    "createdAt": "ISO timestamp",
    "author": "Claude Sonnet 4.5",
    "estimatedDuration": "string",
    "parallelizable": true,
    "maxParallelStories": 5
  }
}`;

  try {
    const response = await client.messages.create({
      model: "claude-sonnet-4-5-20250929",
      max_tokens: 4096,
      system: systemPrompt,
      messages: [
        {
          role: "user",
          content: `Feature Request: ${message}${contextPrompt}

Generate a complete PRD in JSON format. Return ONLY the JSON, no markdown formatting.`,
        },
      ],
    });

    // Extract JSON from response
    const content =
      response.content[0].type === "text" ? response.content[0].text : "";

    // Try to parse JSON, handling markdown code blocks if present
    let jsonStr = content.trim();
    if (jsonStr.startsWith("```")) {
      jsonStr = jsonStr.replace(/^```json?\n/, "").replace(/\n```$/, "");
    }

    const prd = JSON.parse(jsonStr) as PRDFormat;

    // Validate and ensure TDD Iron Law is first criterion
    prd.userStories = prd.userStories.map((story) => ({
      ...story,
      acceptanceCriteria: story.acceptanceCriteria[0] === TDD_IRON_LAW_CRITERION
        ? story.acceptanceCriteria
        : [TDD_IRON_LAW_CRITERION, ...story.acceptanceCriteria],
      passes: false, // Always start as not passing
    }));

    // Ensure metadata has proper timestamp
    if (!prd.metadata.createdAt) {
      prd.metadata.createdAt = new Date().toISOString();
    }

    return prd;
  } catch (error) {
    console.error("Error generating PRD:", error);

    // Fallback PRD for graceful degradation
    return createFallbackPRD(message, context);
  }
}

/**
 * Create a simple fallback PRD when API call fails
 */
function createFallbackPRD(
  message: string,
  context?: CodebaseContext
): PRDFormat {
  const projectName = message
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, "")
    .trim()
    .split(/\s+/)
    .slice(0, 4)
    .join("-");

  return {
    project: projectName || "feature-request",
    branchName: `feature/${projectName || "feature-request"}`,
    description: message,
    domain: context?.technologies?.[0] || "general",
    userStories: [
      {
        id: "US-001",
        title: `Implement: ${message}`,
        description: `As a user, I want ${message} so that the requested feature is available`,
        acceptanceCriteria: [
          TDD_IRON_LAW_CRITERION,
          "Feature implemented according to request",
          "All tests passing",
          "Code passes linting",
        ],
        priority: 1,
        passes: false,
        estimatedComplexity: "medium",
        suggestedModel: "sonnet",
        fileScope: [],
        dependencies: [],
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
      author: "Claude Sonnet 4.5",
      estimatedDuration: "unknown",
      parallelizable: false,
      maxParallelStories: 1,
    },
  };
}
