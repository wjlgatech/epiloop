import type { EpiloopPluginApi } from "epiloop/plugin-sdk";
import { emptyPluginConfigSchema } from "epiloop/plugin-sdk";

import { mattermostPlugin } from "./src/channel.js";
import { setMattermostRuntime } from "./src/runtime.js";

const plugin = {
  id: "mattermost",
  name: "Mattermost",
  description: "Mattermost channel plugin",
  configSchema: emptyPluginConfigSchema(),
  register(api: EpiloopPluginApi) {
    setMattermostRuntime(api.runtime);
    api.registerChannel({ plugin: mattermostPlugin });
  },
};

export default plugin;
