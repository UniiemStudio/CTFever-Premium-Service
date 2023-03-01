import importlib
import logging
import os


class Plugin:
    _logger_name = 'plugin'

    def __init__(self):
        self.logger = logging.getLogger(self._logger_name)

    def __getmethods__(self):
        return [method for method in dir(self)
                if not method.startswith('_')
                and method not in PluginManager.reserved_plugin_methods]

    def load(self):
        raise NotImplementedError('Not yet implemented.')

    def unload(self):
        raise NotImplementedError('Not yet implemented.')

    def activate(self):
        pass

    def deactivate(self):
        pass


class PluginManager:
    reserved_plugin_methods = ['load', 'unload', 'activate', 'deactivate', 'logger']

    def __init__(self, plugin_dir):
        self.logger = logging.getLogger('plugin_manager')
        self.plugin_dir = str(plugin_dir)
        os.path.exists(self.plugin_dir) or os.mkdir(self.plugin_dir)
        self.plugins = {}

    def load_plugins(self):
        for plugin_file in os.listdir(self.plugin_dir):
            if plugin_file.endswith('.py'):
                plugin_name = os.path.splitext(plugin_file)[0]
                self.logger.info(f'load plugin: \033[1;33m{plugin_name}\033[0m')
                plugin_module = importlib.import_module(f'{self.plugin_dir}.{plugin_name}')
                if hasattr(plugin_module, plugin_name.capitalize()):
                    plugin_class = getattr(plugin_module, plugin_name.capitalize())
                    setattr(plugin_class, '_logger_name', f'plug_{plugin_name}')
                    plugin = plugin_class()
                    print(plugin.__getmethods__())
                    try:
                        plugin.load()
                    except NotImplementedError:
                        self.logger.warning(f'plugin \'{plugin_name}\' does not implement load method')
                        continue
                    except Exception as e:
                        self.logger.warning(f'plugin \'{plugin_name}\' failed to load: {e}')
                        continue
                    self.plugins[plugin_name] = plugin
                else:
                    self.logger.warning(f'plugin \'{plugin_name}\' has no class \'{plugin_name.capitalize()}\'')
                    continue

    def unload_plugins(self):
        for plugin_name, plugin in self.plugins.items():
            plugin.unload()

    def activate_plugins(self):
        for plugin_name, plugin in self.plugins.items():
            plugin.activate()

    def deactivate_plugins(self):
        for plugin_name, plugin in self.plugins.items():
            plugin.deactivate()
