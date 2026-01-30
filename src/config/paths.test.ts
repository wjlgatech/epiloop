import path from "node:path";
import { describe, expect, it } from "vitest";

import { resolveOAuthDir, resolveOAuthPath } from "./paths.js";

describe("oauth paths", () => {
  it("prefers EPILOOP_OAUTH_DIR over EPILOOP_STATE_DIR", () => {
    const env = {
      EPILOOP_OAUTH_DIR: "/custom/oauth",
      EPILOOP_STATE_DIR: "/custom/state",
    } as NodeJS.ProcessEnv;

    expect(resolveOAuthDir(env, "/custom/state")).toBe(path.resolve("/custom/oauth"));
    expect(resolveOAuthPath(env, "/custom/state")).toBe(
      path.join(path.resolve("/custom/oauth"), "oauth.json"),
    );
  });

  it("derives oauth path from EPILOOP_STATE_DIR when unset", () => {
    const env = {
      EPILOOP_STATE_DIR: "/custom/state",
    } as NodeJS.ProcessEnv;

    expect(resolveOAuthDir(env, "/custom/state")).toBe(path.join("/custom/state", "credentials"));
    expect(resolveOAuthPath(env, "/custom/state")).toBe(
      path.join("/custom/state", "credentials", "oauth.json"),
    );
  });
});
