from dify_plugin import DifyPluginEnv, Plugin


class BrowserActPluginEnv(DifyPluginEnv):
    MAX_REQUEST_TIMEOUT: int = 900


if __name__ == "__main__":
    plugin = Plugin(BrowserActPluginEnv())
    plugin.run()
