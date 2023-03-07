import importlib
import inspect
import logging
import os
import re
import time
import zipfile

import patoolib
import requests
from tqdm import tqdm

from core.safe import singleton

reserved_plugin_methods = ['load', 'unload', 'activate', 'deactivate', 'logger', 'data_dir', 'fs_write',
                           'params_validater', 'fetch_data_package', 'methods']


class Plugin:
    _plugin_name = 'plugin'
    _logger_name = 'plugin'
    _data_dir = 'data/plugin'

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
                   and method not in reserved_plugin_methods
                   and callable(getattr(self, method))]
        ret = {}
        for method in methods:
            args = inspect.getfullargspec(getattr(self, method)).args
            ret[method] = list(filter(lambda x: x != 'self', args))
        return ret

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

    def methods(self):
        """
        todo: 2023年3月7日15点30分 该接口尚未实现
        重写此方法，告知插件管理器插件公开的方法。该接口会覆盖 __getmethods__
        @see: __getmethods__
        :return: 方法列表
        """
        return None

    # todo: params validater
    def params_validater(self, params):
        """
        重写此方法，在调用时验证参数是否合法
        :param params:  待验证的参数
        :return:        返回任何非 False 表示参数不合法
        """
        return False

    def fetch_data_package(self, url):
        """
        通过 HTTP GET 下载数据包
        :param url: 数据包 URL
        :return:    None
        """
        try:
            req = requests.get(url, stream=True, timeout=10)
        except Exception as e:
            self.logger.error(f'failed to fetch data package: {e}')
            return
        if req.status_code == 200:
            try:
                disposition = req.headers.get('content-disposition', '')
                matches = re.findall('filename=\"(.+)\"', disposition)
                file_name = matches[0] if len(matches) > 0 else url.split('/')[-1].split('?')[0]
                file_size = int(req.headers.get('content-length', 0))
                file_save_path = os.path.join(self._data_dir, file_name)
                if os.path.exists(file_save_path):
                    self.logger.info(f'\033[1;32mpackage already exists: {file_name}\033[0m')
                else:
                    self.logger.info(f'\033[1;32mdownloading package: {file_name} ...\033[0m')
                    time.sleep(0.1)
                    with open(file_save_path, 'wb+') as f, tqdm(
                            desc=file_name,
                            total=file_size,
                            unit='iB',
                            unit_scale=True,
                            unit_divisor=1024,
                            leave=False,
                            smoothing=0.1
                    ) as progress_bar:
                        for chunk in req.iter_content(chunk_size=1024):
                            if chunk:
                                progress_bar.update(f.write(chunk))
                        f.close()
                try:
                    patoolib.extract_archive(
                        file_save_path,
                        outdir=os.path.join(
                            self._data_dir,
                            os.path.splitext(os.path.basename(file_save_path))[0]
                        ),
                        verbosity=-1
                    )
                    # self.logger.info(f'\033[1;32m- extracted package: {file_name}\033[0m')
                except patoolib.util.PatoolError as e:
                    if zipfile.is_zipfile(file_save_path):
                        with zipfile.ZipFile(file_save_path, 'r') as zip_file:
                            zip_file.extractall(os.path.join(
                                self._data_dir,
                                os.path.splitext(os.path.basename(file_save_path))[0]
                            ))
                    else:
                        pass
                except Exception as e:
                    self.logger.error(f'failed to extract data package: {e}', exc_info=True)
            except Exception as e:
                self.logger.error(f'failed to fetch data package: {e}', exc_info=True)
                PluginManager().unload_plugin(self._plugin_name, crash=True)
        else:
            self.logger.error(f'failed to retrieve data package info from {url}')
            PluginManager().unload_plugin(self._plugin_name, crash=True)

    def fs_write(self, filename, content):
        file_path = os.path.join(self._data_dir, filename)
        with open(file_path, 'w+') as f:
            f.write(content)

    def data_dir(self):
        """
        返回插件数据目录
        :return: 数据目录
        """
        return self._data_dir


@singleton
class PluginManager:

    def __init__(self, plugin_dir='plugins', data_dir='data'):
        self.logger = logging.getLogger('plugin_manager')

        self.data_dir = str(data_dir)
        self.plugin_dir = str(plugin_dir)
        os.path.exists(self.data_dir) or os.mkdir(self.data_dir)
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
                    # Assign plugin name and logger name
                    setattr(plugin_class, '_logger_name', f'plugin.{plugin_name}')
                    setattr(plugin_class, '_plugin_name', plugin_name)
                    # Assign a data directory and create it if not exists
                    setattr(plugin_class, '_data_dir', os.path.abspath(f'data/{plugin_name.lower()}'))
                    os.path.exists(getattr(plugin_class, '_data_dir')) or os.mkdir(getattr(plugin_class, '_data_dir'))
                    plugin = plugin_class()
                    try:
                        plugin.load()
                    except NotImplementedError:
                        self.logger.error(f'plugin \'{plugin_name}\' does not implement load method')
                        continue
                    except Exception as e:
                        self.logger.error(f'plugin \'{plugin_name}\' failed to load: {e}')
                        continue
                    self.plugins[plugin_name] = plugin
                else:
                    self.logger.error(f'plugin \'{plugin_name}\' has no class \'{plugin_name.capitalize()}\'')
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

    def unload_plugin(self, plugin_name, crash=False):
        if plugin_name not in self.plugins:
            raise AttributeError(f'\'{plugin_name}\' is not a plugin or never loaded')
        self.plugins[plugin_name].unload()
        self.plugins.pop(plugin_name)
        self.logger.info(f'unload plugin: \033[1;31m{plugin_name}\033[0m{" caused by crash" if crash else ""}')

    def activate_plugins(self):
        for plugin in list(self.plugins.values()):
            plugin.activate()
        # for plugin_name, plugin in self.plugins.items():
        #     plugin.activate()

    def deactivate_plugins(self):
        for plugin_name, plugin in self.plugins.items():
            plugin.deactivate()
