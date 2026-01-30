import type { EpiloopPluginApi } from "epiloop/plugin-sdk";
import { emptyPluginConfigSchema } from "epiloop/plugin-sdk";

import { msteamsPlugin } from "./src/channel.js";
import { setMSTeamsRuntime } from "./src/runtime.js";

const plugin = {
  id: "msteams",
  name: "Microsoft Teams",
  description: "Microsoft Teams channel plugin (Bot Framework)",
  configSchema: emptyPluginConfigSchema(),
  register(api: EpiloopPluginApi) {
    setMSTeamsRuntime(api.runtime);
    api.registerChannel({ plugin: msteamsPlugin });
  },
};

export default plugin;
