import type { EpiloopPluginApi } from "epiloop/plugin-sdk";
import { emptyPluginConfigSchema } from "epiloop/plugin-sdk";

import { tlonPlugin } from "./src/channel.js";
import { setTlonRuntime } from "./src/runtime.js";

const plugin = {
  id: "tlon",
  name: "Tlon",
  description: "Tlon/Urbit channel plugin",
  configSchema: emptyPluginConfigSchema(),
  register(api: EpiloopPluginApi) {
    setTlonRuntime(api.runtime);
    api.registerChannel({ plugin: tlonPlugin });
  },
};

export default plugin;
