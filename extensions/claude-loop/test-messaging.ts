#!/usr/bin/env tsx
/**
 * Test Messaging Bridge Integration
 * Verifies WhatsApp/Google Chat command parsing and response formatting
 */

import { createMessagingBridge } from "./src/messaging-bridge.js";
import { AutonomousCodingSkill } from "./src/skill-handler.js";
import type { MessageContext } from "./src/messaging-bridge.js";
import * as path from "path";
import { fileURLToPath } from "url";
import { dirname } from "path";
import * as os from "os";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

console.log("=".repeat(60));
console.log("Messaging Bridge Integration Test");
console.log("=".repeat(60));
console.log();

// Create test skill instance
const testDir = path.join(os.tmpdir(), "test-messaging-" + Date.now());
const skill = new AutonomousCodingSkill({
  workspaceRoot: testDir,
  claudeLoopPath: "/Users/jialiang.wu/Documents/Projects/claude-loop/claude-loop.sh",
  maxConcurrentSessions: 3,
});

// Create messaging bridge
const bridge = createMessagingBridge(skill);

// Test context
const testContext: MessageContext = {
  userId: "test-user-123",
  channelId: "test-channel",
  messageId: "msg-001",
  platform: "whatsapp",
};

// Test cases
async function runTests() {
  let passed = 0;
  let failed = 0;

  console.log("📋 Test 1: Invalid Command");
  try {
    const response = await bridge.handleMessage("/autonomous-coding invalid", testContext);
    if (response.includes("Usage:")) {
      console.log("✅ PASS - Returns usage message");
      passed++;
    } else {
      console.log("❌ FAIL - Expected usage message");
      console.log("   Got:", response);
      failed++;
    }
  } catch (error) {
    console.log("❌ FAIL -", error);
    failed++;
  }
  console.log();

  console.log("📋 Test 2: List Sessions Command");
  try {
    const response = await bridge.handleMessage("/autonomous-coding list", testContext);
    if (response.includes("📋")) {
      console.log("✅ PASS - Returns formatted list");
      console.log("   Response:", response.split("\n")[0]);
      passed++;
    } else {
      console.log("❌ FAIL - Expected list response");
      console.log("   Got:", response);
      failed++;
    }
  } catch (error) {
    console.log("❌ FAIL -", error);
    failed++;
  }
  console.log();

  console.log("📋 Test 3: Status Non-Existent Session");
  try {
    const response = await bridge.handleMessage(
      "/autonomous-coding status --session fake-id",
      testContext
    );
    if (response.includes("❌")) {
      console.log("✅ PASS - Returns error message");
      passed++;
    } else {
      console.log("❌ FAIL - Expected error message");
      console.log("   Got:", response);
      failed++;
    }
  } catch (error) {
    console.log("❌ FAIL -", error);
    failed++;
  }
  console.log();

  console.log("📋 Test 4: Start with Description");
  try {
    const response = await bridge.handleMessage(
      "/autonomous-coding start Add a hello world function",
      testContext
    );
    if (response.includes("🚀") || response.includes("Session ID")) {
      console.log("✅ PASS - Returns start confirmation");
      console.log("   First line:", response.split("\n")[0]);
      passed++;
    } else {
      console.log("❌ FAIL - Expected start confirmation");
      console.log("   Got:", response);
      failed++;
    }
  } catch (error) {
    console.log("❌ FAIL -", error);
    failed++;
  }
  console.log();

  console.log("📋 Test 5: Format Progress Update");
  try {
    const progressMsg = bridge.formatProgressUpdate({
      progress: 45,
      currentStory: "US-002: Implement feature X",
      completedStories: 2,
      totalStories: 5,
    });
    if (progressMsg.includes("📊") && progressMsg.includes("45%")) {
      console.log("✅ PASS - Formats progress correctly");
      passed++;
    } else {
      console.log("❌ FAIL - Progress format incorrect");
      console.log("   Got:", progressMsg);
      failed++;
    }
  } catch (error) {
    console.log("❌ FAIL -", error);
    failed++;
  }
  console.log();

  console.log("📋 Test 6: Format Completion Message");
  try {
    const completionMsg = bridge.formatCompletionMessage({
      sessionId: "test-session-123",
      duration: 1800000,
      completedStories: 5,
      totalStories: 5,
    });
    if (completionMsg.includes("🎉") && completionMsg.includes("30 minutes")) {
      console.log("✅ PASS - Formats completion correctly");
      passed++;
    } else {
      console.log("❌ FAIL - Completion format incorrect");
      console.log("   Got:", completionMsg);
      failed++;
    }
  } catch (error) {
    console.log("❌ FAIL -", error);
    failed++;
  }
  console.log();

  console.log("📋 Test 7: Format Error Message");
  try {
    const errorMsg = bridge.formatErrorMessage(new Error("Test error occurred"));
    if (errorMsg.includes("❌") && errorMsg.includes("Test error occurred")) {
      console.log("✅ PASS - Formats error correctly");
      passed++;
    } else {
      console.log("❌ FAIL - Error format incorrect");
      console.log("   Got:", errorMsg);
      failed++;
    }
  } catch (error) {
    console.log("❌ FAIL -", error);
    failed++;
  }
  console.log();

  console.log("📋 Test 8: WhatsApp Platform Context");
  try {
    const response = await bridge.handleMessage(
      "/autonomous-coding list",
      { ...testContext, platform: "whatsapp" }
    );
    if (typeof response === "string") {
      console.log("✅ PASS - Handles WhatsApp context");
      passed++;
    } else {
      console.log("❌ FAIL - Response format incorrect for WhatsApp");
      failed++;
    }
  } catch (error) {
    console.log("❌ FAIL -", error);
    failed++;
  }
  console.log();

  console.log("📋 Test 9: Google Chat Platform Context");
  try {
    const response = await bridge.handleMessage(
      "/autonomous-coding list",
      { ...testContext, platform: "googlechat" }
    );
    if (typeof response === "string") {
      console.log("✅ PASS - Handles Google Chat context");
      passed++;
    } else {
      console.log("❌ FAIL - Response format incorrect for Google Chat");
      failed++;
    }
  } catch (error) {
    console.log("❌ FAIL -", error);
    failed++;
  }
  console.log();

  // Summary
  console.log("=".repeat(60));
  console.log("Test Results Summary");
  console.log("=".repeat(60));
  console.log(`✅ Passed: ${passed}/9`);
  console.log(`❌ Failed: ${failed}/9`);
  console.log(`Success Rate: ${Math.round((passed / 9) * 100)}%`);
  console.log();

  if (failed === 0) {
    console.log("🎉 All messaging bridge tests passed!");
    console.log("   Ready for WhatsApp/Google Chat integration");
  } else {
    console.log("⚠️  Some tests failed - review implementation");
  }
}

runTests().catch(console.error);
