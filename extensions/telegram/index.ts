import type { EpiloopPluginApi } from "epiloop/plugin-sdk";
import { emptyPluginConfigSchema } from "epiloop/plugin-sdk";

import { telegramPlugin } from "./src/channel.js";
import { setTelegramRuntime } from "./src/runtime.js";

const plugin = {
  id: "telegram",
  name: "Telegram",
  description: "Telegram channel plugin",
  configSchema: emptyPluginConfigSchema(),
  register(api: EpiloopPluginApi) {
    setTelegramRuntime(api.runtime);
    api.registerChannel({ plugin: telegramPlugin });
  },
};

export default plugin;
