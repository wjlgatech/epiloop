import { createRequire } from "node:module";

declare const __EPILOOP_VERSION__: string | undefined;

function readVersionFromPackageJson(): string | null {
  try {
    const require = createRequire(import.meta.url);
    const pkg = require("../package.json") as { version?: string };
    return pkg.version ?? null;
  } catch {
    return null;
  }
}

// Single source of truth for the current epiloop version.
// - Embedded/bundled builds: injected define or env var.
// - Dev/npm builds: package.json.
export const VERSION =
  (typeof __EPILOOP_VERSION__ === "string" && __EPILOOP_VERSION__) ||
  process.env.EPILOOP_BUNDLED_VERSION ||
  readVersionFromPackageJson() ||
  "0.0.0";
