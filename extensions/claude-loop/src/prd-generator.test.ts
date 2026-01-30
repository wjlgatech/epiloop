import { describe, it, expect, vi, beforeEach } from "vitest";
import { convertMessageToPRD } from "./prd-generator";
import type { CodebaseContext, PRDFormat } from "./types";

describe("PRD Generator - RED Phase (TDD)", () => {
  const mockContext: CodebaseContext = {
    repoPath: "/test/repo",
    technologies: ["typescript", "node"],
    testingFramework: "vitest",
    lintConfig: "oxlint",
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("convertMessageToPRD", () => {
    it("should convert simple feature request to PRD format", async () => {
      const message = "Add a login button to the homepage";

      const result = await convertMessageToPRD(message, mockContext);

      expect(result).toBeDefined();
      expect(result.project).toContain("login");
      expect(result.userStories).toHaveLength(1);
      expect(result.userStories[0].title).toContain("login");
      expect(result.userStories[0].acceptanceCriteria).toContain(
        expect.stringMatching(/TDD|test.*first/i)
      );
    });

    it("should convert complex feature request with multiple stories", async () => {
      const message =
        "Build a user authentication system with login, signup, password reset, and session management";

      const result = await convertMessageToPRD(message, mockContext);

      expect(result.userStories.length).toBeGreaterThan(1);
      expect(result.userStories.length).toBeLessThanOrEqual(8);
      expect(result.userStories.every((s) => s.id.startsWith("US-"))).toBe(
        true
      );
      expect(result.userStories.every((s) => s.priority > 0)).toBe(true);
    });

    it("should include TDD Iron Law as first acceptance criterion", async () => {
      const message = "Add a search feature";

      const result = await convertMessageToPRD(message, mockContext);

      result.userStories.forEach((story) => {
        const firstCriterion = story.acceptanceCriteria[0];
        expect(firstCriterion).toMatch(
          /Tests written FIRST.*RED.*GREEN.*TDD Iron Law/i
        );
      });
    });

    it("should assign appropriate complexity estimates", async () => {
      const message = "Add a button vs Build a full OAuth2 authentication flow";

      const result = await convertMessageToPRD(message, mockContext);

      const complexities = result.userStories.map((s) => s.estimatedComplexity);
      expect(complexities).toContain("simple");
    });

    it("should suggest appropriate models for complex stories", async () => {
      const message =
        "Refactor the entire database layer to support multiple backends";

      const result = await convertMessageToPRD(message, mockContext);

      const complexStories = result.userStories.filter(
        (s) => s.estimatedComplexity === "complex"
      );
      complexStories.forEach((story) => {
        expect(["sonnet", "opus"]).toContain(story.suggestedModel);
      });
    });

    it("should handle vague feature descriptions", async () => {
      const message = "Make it better";

      const result = await convertMessageToPRD(message, mockContext);

      expect(result.userStories.length).toBeGreaterThan(0);
      expect(result.description).toBeDefined();
      expect(result.description.length).toBeGreaterThan(0);
    });

    it("should use codebase context to determine file scope", async () => {
      const contextWithFiles: CodebaseContext = {
        ...mockContext,
        existingFiles: [
          "src/components/Button.tsx",
          "src/styles/button.css",
          "src/tests/button.test.ts",
        ],
      };

      const message = "Update the button component styling";

      const result = await convertMessageToPRD(message, contextWithFiles);

      const fileScopes = result.userStories.flatMap((s) => s.fileScope || []);
      expect(fileScopes.some((f) => f.includes("Button"))).toBe(true);
    });

    it("should generate proper quality gates", async () => {
      const message = "Add feature X";

      const result = await convertMessageToPRD(message, mockContext);

      expect(result.qualityGates).toEqual({
        requireTests: true,
        requireTypecheck: true,
        requireLint: true,
        minCoverage: 75,
        securityScan: true,
      });
    });

    it("should create valid branch names", async () => {
      const message = "Add OAuth2 Login Feature";

      const result = await convertMessageToPRD(message, mockContext);

      expect(result.branchName).toMatch(/^feature\/[a-z0-9-]+$/);
      expect(result.branchName).not.toContain(" ");
      expect(result.branchName).not.toContain("_");
    });

    it("should detect domain from feature description", async () => {
      const message = "Add GraphQL API endpoint for user queries";

      const result = await convertMessageToPRD(message, mockContext);

      expect(result.domain).toMatch(/api|backend|graphql/i);
    });

    it("should handle missing context gracefully", async () => {
      const message = "Add a feature";

      const result = await convertMessageToPRD(message);

      expect(result).toBeDefined();
      expect(result.userStories).toHaveLength(1);
    });

    it("should set dependencies between stories correctly", async () => {
      const message =
        "Build user authentication: first create user model, then login endpoint, then session management";

      const result = await convertMessageToPRD(message, mockContext);

      const storiesWithDeps = result.userStories.filter(
        (s) => s.dependencies && s.dependencies.length > 0
      );
      expect(storiesWithDeps.length).toBeGreaterThan(0);

      storiesWithDeps.forEach((story) => {
        story.dependencies?.forEach((dep) => {
          expect(result.userStories.some((s) => s.id === dep)).toBe(true);
        });
      });
    });

    it("should generate timestamps in ISO format", async () => {
      const message = "Add feature";

      const result = await convertMessageToPRD(message, mockContext);

      const timestamp = result.metadata.createdAt;
      expect(() => new Date(timestamp)).not.toThrow();
      expect(timestamp).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/);
    });

    it("should mark all stories as not passing initially", async () => {
      const message = "Add multiple features";

      const result = await convertMessageToPRD(message, mockContext);

      result.userStories.forEach((story) => {
        expect(story.passes).toBe(false);
      });
    });

    it("should handle API errors gracefully", async () => {
      // This test would need mocking of the Claude API
      // For now, we expect the function to throw or return a fallback PRD
      const message = "Add feature";

      // Should not throw
      await expect(convertMessageToPRD(message, mockContext)).resolves.toBeDefined();
    });
  });
});
