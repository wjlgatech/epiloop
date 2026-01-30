import type { EpiloopPluginApi } from "epiloop/plugin-sdk";
import { emptyPluginConfigSchema } from "epiloop/plugin-sdk";

import { createDiagnosticsOtelService } from "./src/service.js";

const plugin = {
  id: "diagnostics-otel",
  name: "Diagnostics OpenTelemetry",
  description: "Export diagnostics events to OpenTelemetry",
  configSchema: emptyPluginConfigSchema(),
  register(api: EpiloopPluginApi) {
    api.registerService(createDiagnosticsOtelService());
  },
};

export default plugin;
