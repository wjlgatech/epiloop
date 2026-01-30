/**
 * Test real autonomous coding session
 */

import { AutonomousCodingSkill } from "./src/skill-handler.js";
import { loadConfig } from "./src/config.js";
import * as path from "path";

console.log("=".repeat(60));
console.log("Claude-Loop Extension - Real Session Test");
console.log("=".repeat(60));

async function testRealSession() {
  try {
    const config = loadConfig();
    const skill = new AutonomousCodingSkill({
      workspaceRoot: config.claudeLoop.workspaceRoot,
      claudeLoopPath: path.join(config.claudeLoop.path, "claude-loop.sh"),
      maxConcurrentSessions: config.workspace.maxConcurrentPerUser,
    });

    // Subscribe to events
    skill.on("progress", (data) => {
      console.log(`\n📊 Progress: ${data.progress}% - ${data.currentStory || "starting"}`);
    });

    skill.on("story-complete", (data) => {
      console.log(`\n✅ Story ${data.storyId} completed in ${data.duration}ms`);
    });

    skill.on("complete", (data) => {
      console.log(`\n🎉 Autonomous implementation completed!`);
      console.log(`   Duration: ${data.duration}ms`);
      console.log(`   Completed stories: ${data.completedStories}/${data.totalStories}`);
    });

    skill.on("error", (data) => {
      console.error(`\n❌ Error in session ${data.sessionId}:`, data.error);
    });

    console.log("\n🚀 Starting autonomous coding session...");
    console.log("   Feature: Add a factorial function");
    console.log("   This will:");
    console.log("   1. Generate PRD using Claude API");
    console.log("   2. Execute implementation with RG-TDD");
    console.log("   3. Run quality gates");
    console.log("   4. Report progress\n");

    const result = await skill.handleCommand("start", {
      message: "Add a function to calculate factorial of a number with tests",
      userId: "test-user-real",
    });

    if (result.success) {
      console.log("✅ Session started successfully!");
      console.log("   Session ID:", result.sessionId);
      console.log("\n📋 Generated PRD:");
      if (result.prdPreview) {
        console.log("   Project:", result.prdPreview.project);
        console.log("   Description:", result.prdPreview.description);
        console.log("   Stories:", result.prdPreview.userStories?.length || 0);
        result.prdPreview.userStories?.forEach((story, i) => {
          console.log(`   ${i + 1}. ${story.id}: ${story.title}`);
        });
      }

      // Wait a bit for the session to start executing
      console.log("\n⏳ Waiting for execution to begin...");
      await new Promise(resolve => setTimeout(resolve, 5000));

      // Check status
      console.log("\n📊 Checking session status...");
      const statusResult = await skill.handleCommand("status", {
        sessionId: result.sessionId,
        userId: "test-user-real",
      });

      if (statusResult.success) {
        console.log("✅ Status retrieved:");
        console.log("   Running:", statusResult.isRunning);
        if (statusResult.progress) {
          console.log("   Progress:", `${statusResult.progress.percent}%`);
          console.log("   Current story:", statusResult.progress.currentStory);
          console.log("   Completed:", `${statusResult.progress.completedStories}/${statusResult.progress.totalStories}`);
        }
      }

      // Note: Actual execution will take several minutes
      console.log("\n📝 Note: The autonomous execution is now running in the background.");
      console.log("   This may take 5-30 minutes depending on complexity.");
      console.log("   Monitor progress with: /autonomous-coding status --session " + result.sessionId);
      console.log("   View logs at: ~/.epiloop/logs/claude-loop/");

    } else {
      console.error("❌ Failed to start session:", result.message);
    }

  } catch (error) {
    console.error("\n❌ Test failed:", error);
    if (error instanceof Error) {
      console.error("   Stack:", error.stack);
    }
    process.exit(1);
  }
}

testRealSession();
