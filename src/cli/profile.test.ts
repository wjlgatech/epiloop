import path from "node:path";
import { describe, expect, it } from "vitest";
import { formatCliCommand } from "./command-format.js";
import { applyCliProfileEnv, parseCliProfileArgs } from "./profile.js";

describe("parseCliProfileArgs", () => {
  it("leaves gateway --dev for subcommands", () => {
    const res = parseCliProfileArgs([
      "node",
      "epiloop",
      "gateway",
      "--dev",
      "--allow-unconfigured",
    ]);
    if (!res.ok) throw new Error(res.error);
    expect(res.profile).toBeNull();
    expect(res.argv).toEqual(["node", "epiloop", "gateway", "--dev", "--allow-unconfigured"]);
  });

  it("still accepts global --dev before subcommand", () => {
    const res = parseCliProfileArgs(["node", "epiloop", "--dev", "gateway"]);
    if (!res.ok) throw new Error(res.error);
    expect(res.profile).toBe("dev");
    expect(res.argv).toEqual(["node", "epiloop", "gateway"]);
  });

  it("parses --profile value and strips it", () => {
    const res = parseCliProfileArgs(["node", "epiloop", "--profile", "work", "status"]);
    if (!res.ok) throw new Error(res.error);
    expect(res.profile).toBe("work");
    expect(res.argv).toEqual(["node", "epiloop", "status"]);
  });

  it("rejects missing profile value", () => {
    const res = parseCliProfileArgs(["node", "epiloop", "--profile"]);
    expect(res.ok).toBe(false);
  });

  it("rejects combining --dev with --profile (dev first)", () => {
    const res = parseCliProfileArgs(["node", "epiloop", "--dev", "--profile", "work", "status"]);
    expect(res.ok).toBe(false);
  });

  it("rejects combining --dev with --profile (profile first)", () => {
    const res = parseCliProfileArgs(["node", "epiloop", "--profile", "work", "--dev", "status"]);
    expect(res.ok).toBe(false);
  });
});

describe("applyCliProfileEnv", () => {
  it("fills env defaults for dev profile", () => {
    const env: Record<string, string | undefined> = {};
    applyCliProfileEnv({
      profile: "dev",
      env,
      homedir: () => "/home/peter",
    });
    const expectedStateDir = path.join("/home/peter", ".epiloop-dev");
    expect(env.EPILOOP_PROFILE).toBe("dev");
    expect(env.EPILOOP_STATE_DIR).toBe(expectedStateDir);
    expect(env.EPILOOP_CONFIG_PATH).toBe(path.join(expectedStateDir, "epiloop.json"));
    expect(env.EPILOOP_GATEWAY_PORT).toBe("19001");
  });

  it("does not override explicit env values", () => {
    const env: Record<string, string | undefined> = {
      EPILOOP_STATE_DIR: "/custom",
      EPILOOP_GATEWAY_PORT: "19099",
    };
    applyCliProfileEnv({
      profile: "dev",
      env,
      homedir: () => "/home/peter",
    });
    expect(env.EPILOOP_STATE_DIR).toBe("/custom");
    expect(env.EPILOOP_GATEWAY_PORT).toBe("19099");
    expect(env.EPILOOP_CONFIG_PATH).toBe(path.join("/custom", "epiloop.json"));
  });
});

describe("formatCliCommand", () => {
  it("returns command unchanged when no profile is set", () => {
    expect(formatCliCommand("epiloop doctor --fix", {})).toBe("epiloop doctor --fix");
  });

  it("returns command unchanged when profile is default", () => {
    expect(formatCliCommand("epiloop doctor --fix", { EPILOOP_PROFILE: "default" })).toBe(
      "epiloop doctor --fix",
    );
  });

  it("returns command unchanged when profile is Default (case-insensitive)", () => {
    expect(formatCliCommand("epiloop doctor --fix", { EPILOOP_PROFILE: "Default" })).toBe(
      "epiloop doctor --fix",
    );
  });

  it("returns command unchanged when profile is invalid", () => {
    expect(formatCliCommand("epiloop doctor --fix", { EPILOOP_PROFILE: "bad profile" })).toBe(
      "epiloop doctor --fix",
    );
  });

  it("returns command unchanged when --profile is already present", () => {
    expect(
      formatCliCommand("epiloop --profile work doctor --fix", { EPILOOP_PROFILE: "work" }),
    ).toBe("epiloop --profile work doctor --fix");
  });

  it("returns command unchanged when --dev is already present", () => {
    expect(formatCliCommand("epiloop --dev doctor", { EPILOOP_PROFILE: "dev" })).toBe(
      "epiloop --dev doctor",
    );
  });

  it("inserts --profile flag when profile is set", () => {
    expect(formatCliCommand("epiloop doctor --fix", { EPILOOP_PROFILE: "work" })).toBe(
      "epiloop --profile work doctor --fix",
    );
  });

  it("trims whitespace from profile", () => {
    expect(formatCliCommand("epiloop doctor --fix", { EPILOOP_PROFILE: "  jbclawd  " })).toBe(
      "epiloop --profile jbclawd doctor --fix",
    );
  });

  it("handles command with no args after epiloop", () => {
    expect(formatCliCommand("epiloop", { EPILOOP_PROFILE: "test" })).toBe("epiloop --profile test");
  });

  it("handles pnpm wrapper", () => {
    expect(formatCliCommand("pnpm epiloop doctor", { EPILOOP_PROFILE: "work" })).toBe(
      "pnpm epiloop --profile work doctor",
    );
  });
});
