import type { EpiloopPluginApi } from "epiloop/plugin-sdk";
import { emptyPluginConfigSchema } from "epiloop/plugin-sdk";

import { discordPlugin } from "./src/channel.js";
import { setDiscordRuntime } from "./src/runtime.js";

const plugin = {
  id: "discord",
  name: "Discord",
  description: "Discord channel plugin",
  configSchema: emptyPluginConfigSchema(),
  register(api: EpiloopPluginApi) {
    setDiscordRuntime(api.runtime);
    api.registerChannel({ plugin: discordPlugin });
  },
};

export default plugin;
