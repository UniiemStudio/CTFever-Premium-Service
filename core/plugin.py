import importlib
import logging
import inspect
import os

from core.safe import singleton

reserved_plugin_methods = ['load', 'unload', 'activate', 'deactivate', 'logger']


class Plugin:
    _logger_name = 'plugin'

    def __init__(self):
        self.logger = logging.getLogger(self._logger_name)

    async def __callmethod__(self, method_name, *args, **kwargs):
        """
        调用插件公开的方法
        :param method_name: 方法名
        :param args:        参数
        :param kwargs:      键值对参数
        :return:            执行结果
        """
        if method_name in reserved_plugin_methods:
            raise AttributeError(f'cannot call reserved method \'{method_name}\'')
        elif method_name not in self.__getmethods__():
            raise AttributeError(f'\'{method_name}\' is not a method')
        method = getattr(self, method_name)
        if callable(method):
            if inspect.iscoroutinefunction(method):
                return await method(*args, **kwargs)
            else:
                return method(*args, **kwargs)
        else:
            raise AttributeError(f'\'{method_name}\' is not callable')

    def __getmethods__(self):
        """
        获取插件除保留方法外的所有方法
        :return: 方法名列表
        """
        methods = [method for method in dir(self)
                   if not method.startswith('_')
                   and method not in reserved_plugin_methods]
        ret = {}
        for method in methods:
            args = inspect.getfullargspec(getattr(self, method)).args
            ret[method] = list(filter(lambda x: x != 'self', args))
        return ret

    # todo: params validater
    def params_validater(self, params):
        """
        重写此方法，在调用时验证参数是否合法
        :param params:  待验证的参数
        :return:        参数是否合法
        """
        return True

    def load(self):
        """
        插件被加载时将调用此方法
        * 该方法必须重写
        """
        raise NotImplementedError('Not yet implemented.')

    def unload(self):
        """
        插件被卸载时将调用此方法
        * 该方法必须重写
        """
        raise NotImplementedError('Not yet implemented.')

    def activate(self):
        pass

    def deactivate(self):
        pass


@singleton
class PluginManager:

    def __init__(self, plugin_dir='plugins'):
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

    async def call_plugin_method(self, plugin_name, method_name, *args, **kwargs):
        if plugin_name not in self.plugins:
            raise AttributeError(f'\'{plugin_name}\' is not a plugin')
        plugin = self.plugins[plugin_name]
        if method_name not in plugin.__getmethods__():
            raise AttributeError(f'Plugin \'{plugin_name}\' has no method \'{method_name}\'')
        if len(plugin.__getmethods__()[method_name]) == 0:
            return await plugin.__callmethod__(method_name)
        if len(plugin.__getmethods__()[method_name]) != len(args):
            raise AttributeError(f'\'{method_name}\' takes {len(plugin.__getmethods__()[method_name])} arguments '
                                 f'({len(args)} given)')
        return await plugin.__callmethod__(method_name, *args, **kwargs)

    def get_plugin_logger(self, plugin_name):
        if plugin_name not in self.plugins:
            raise AttributeError(f'\'{plugin_name}\' is not a plugin')
        else:
            if hasattr(self.plugins[plugin_name], 'logger'):
                return getattr(self.plugins[plugin_name], 'logger')
        return logging.getLogger(f'plug_mgr:{plugin_name}')

    def unload_plugins(self):
        for plugin_name, plugin in self.plugins.items():
            plugin.unload()

    def activate_plugins(self):
        for plugin_name, plugin in self.plugins.items():
            plugin.activate()

    def deactivate_plugins(self):
        for plugin_name, plugin in self.plugins.items():
            plugin.deactivate()
