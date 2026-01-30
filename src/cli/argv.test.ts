import { describe, expect, it } from "vitest";

import {
  buildParseArgv,
  getFlagValue,
  getCommandPath,
  getPrimaryCommand,
  getPositiveIntFlagValue,
  getVerboseFlag,
  hasHelpOrVersion,
  hasFlag,
  shouldMigrateState,
  shouldMigrateStateFromPath,
} from "./argv.js";

describe("argv helpers", () => {
  it("detects help/version flags", () => {
    expect(hasHelpOrVersion(["node", "epiloop", "--help"])).toBe(true);
    expect(hasHelpOrVersion(["node", "epiloop", "-V"])).toBe(true);
    expect(hasHelpOrVersion(["node", "epiloop", "status"])).toBe(false);
  });

  it("extracts command path ignoring flags and terminator", () => {
    expect(getCommandPath(["node", "epiloop", "status", "--json"], 2)).toEqual(["status"]);
    expect(getCommandPath(["node", "epiloop", "agents", "list"], 2)).toEqual(["agents", "list"]);
    expect(getCommandPath(["node", "epiloop", "status", "--", "ignored"], 2)).toEqual(["status"]);
  });

  it("returns primary command", () => {
    expect(getPrimaryCommand(["node", "epiloop", "agents", "list"])).toBe("agents");
    expect(getPrimaryCommand(["node", "epiloop"])).toBeNull();
  });

  it("parses boolean flags and ignores terminator", () => {
    expect(hasFlag(["node", "epiloop", "status", "--json"], "--json")).toBe(true);
    expect(hasFlag(["node", "epiloop", "--", "--json"], "--json")).toBe(false);
  });

  it("extracts flag values with equals and missing values", () => {
    expect(getFlagValue(["node", "epiloop", "status", "--timeout", "5000"], "--timeout")).toBe(
      "5000",
    );
    expect(getFlagValue(["node", "epiloop", "status", "--timeout=2500"], "--timeout")).toBe("2500");
    expect(getFlagValue(["node", "epiloop", "status", "--timeout"], "--timeout")).toBeNull();
    expect(getFlagValue(["node", "epiloop", "status", "--timeout", "--json"], "--timeout")).toBe(
      null,
    );
    expect(getFlagValue(["node", "epiloop", "--", "--timeout=99"], "--timeout")).toBeUndefined();
  });

  it("parses verbose flags", () => {
    expect(getVerboseFlag(["node", "epiloop", "status", "--verbose"])).toBe(true);
    expect(getVerboseFlag(["node", "epiloop", "status", "--debug"])).toBe(false);
    expect(getVerboseFlag(["node", "epiloop", "status", "--debug"], { includeDebug: true })).toBe(
      true,
    );
  });

  it("parses positive integer flag values", () => {
    expect(getPositiveIntFlagValue(["node", "epiloop", "status"], "--timeout")).toBeUndefined();
    expect(
      getPositiveIntFlagValue(["node", "epiloop", "status", "--timeout"], "--timeout"),
    ).toBeNull();
    expect(
      getPositiveIntFlagValue(["node", "epiloop", "status", "--timeout", "5000"], "--timeout"),
    ).toBe(5000);
    expect(
      getPositiveIntFlagValue(["node", "epiloop", "status", "--timeout", "nope"], "--timeout"),
    ).toBeUndefined();
  });

  it("builds parse argv from raw args", () => {
    const nodeArgv = buildParseArgv({
      programName: "epiloop",
      rawArgs: ["node", "epiloop", "status"],
    });
    expect(nodeArgv).toEqual(["node", "epiloop", "status"]);

    const directArgv = buildParseArgv({
      programName: "epiloop",
      rawArgs: ["epiloop", "status"],
    });
    expect(directArgv).toEqual(["node", "epiloop", "status"]);

    const bunArgv = buildParseArgv({
      programName: "epiloop",
      rawArgs: ["bun", "src/entry.ts", "status"],
    });
    expect(bunArgv).toEqual(["bun", "src/entry.ts", "status"]);
  });

  it("builds parse argv from fallback args", () => {
    const fallbackArgv = buildParseArgv({
      programName: "epiloop",
      fallbackArgv: ["status"],
    });
    expect(fallbackArgv).toEqual(["node", "epiloop", "status"]);
  });

  it("decides when to migrate state", () => {
    expect(shouldMigrateState(["node", "epiloop", "status"])).toBe(false);
    expect(shouldMigrateState(["node", "epiloop", "health"])).toBe(false);
    expect(shouldMigrateState(["node", "epiloop", "sessions"])).toBe(false);
    expect(shouldMigrateState(["node", "epiloop", "memory", "status"])).toBe(false);
    expect(shouldMigrateState(["node", "epiloop", "agent", "--message", "hi"])).toBe(false);
    expect(shouldMigrateState(["node", "epiloop", "agents", "list"])).toBe(true);
    expect(shouldMigrateState(["node", "epiloop", "message", "send"])).toBe(true);
  });

  it("reuses command path for migrate state decisions", () => {
    expect(shouldMigrateStateFromPath(["status"])).toBe(false);
    expect(shouldMigrateStateFromPath(["agents", "list"])).toBe(true);
  });
});
