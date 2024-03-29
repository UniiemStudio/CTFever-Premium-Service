import hashlib
import importlib
import inspect
import json
import logging
import os
import re
import shutil
import time
import zipfile
from typing import List

import patoolib
import requests
from fastapi import UploadFile
from tqdm import tqdm

from core.safe import singleton

reserved_plugin_methods = ['load', 'unload', 'activate', 'deactivate', 'logger', 'data_dir', 'fs_write',
                           'params_validater', 'fetch_data_package', 'methods', 'ConfigUtil',
                           'save_upload_file_as_temporary', 'keep_temporary_file', 'purge_temporary_files']


class Plugin:
    _plugin_name = 'plugin'
    _logger_name = 'plugin'
    _data_dir = 'data/plugin'
    _temp_dir = 'data/plugin/temp'

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

    def __getmethods__(self, exclude: List[str] = None):
        """
        获取插件除保留方法外的所有方法
        :param exclude: 排除的方法名列表
        :return:        方法名列表
        """
        methods = [method for method in dir(self)
                   if not method.startswith('_')
                   and method not in reserved_plugin_methods
                   and callable(getattr(self, method))]
        ret = {}
        for method in methods:
            args = inspect.getfullargspec(getattr(self, method)).args
            ret[method] = list(filter(lambda x: x != 'self', args))
        if exclude:
            for method in exclude:
                if method in ret:
                    ret.pop(method)
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
                        verbosity=-1,
                        interactive=False
                    )
                    # self.logger.info(f'\033[1;32m- extracted package: {file_name}\033[0m')
                except patoolib.util.PatoolError as e:
                    if zipfile.is_zipfile(file_save_path):
                        with zipfile.ZipFile(file_save_path, 'r') as zip_file:
                            extract_folder = os.path.join(
                                self._data_dir,
                                os.path.splitext(os.path.basename(file_save_path))[0],
                            )
                            # zip_file.extractall(extract_folder)
                            for member in zip_file.namelist():
                                target_path = os.path.join(extract_folder, member)
                                if os.path.exists(target_path):
                                    os.remove(target_path)
                                zip_file.extract(member, path=extract_folder)
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

    async def save_upload_file_as_temporary(self, file: UploadFile, sub_dir: str = ''):
        origin_name = file.filename
        origin_basename, origin_ext = os.path.splitext(origin_name)
        temporal_name = f'{origin_basename}_{hashlib.md5(str(time.time()).encode()).hexdigest()[:6]}{origin_ext}'
        file_content = await file.read()
        file_save_path = os.path.join(self._temp_dir, sub_dir, temporal_name)
        file_save_dir = os.path.dirname(file_save_path)
        if not os.path.exists(file_save_dir):
            os.makedirs(file_save_dir)
        with open(file_save_path, 'wb') as f:
            f.write(file_content)
        return file_save_path, file_save_dir

    def keep_temporary_file(self, keep_count: int = 10):
        if len(os.listdir(self._temp_dir)) > keep_count:
            files = os.listdir(self._temp_dir)
            files.sort(key=lambda fn: os.path.getmtime(os.path.join(self._temp_dir, fn)))
            os.remove(os.path.join(self._temp_dir, files[0]))

    def purge_temporary_files(self):
        shutil.rmtree(self._temp_dir)
        os.mkdir(self._temp_dir)

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

    class ConfigUtil:
        def __init__(self, data_dir: str, cfg_name: str = 'config.json', default_cfg=None):
            self.default_cfg = default_cfg
            if self.default_cfg is None:
                self.default_cfg = {}
            self.cfg_path = os.path.join(data_dir, cfg_name)
            self.cfg = self.read_cfg()

        def read_cfg(self):
            if not os.path.exists(self.cfg_path):
                with open(self.cfg_path, 'w', encoding='utf-8') as f:
                    f.write(json.dumps(self.default_cfg))
            with open(self.cfg_path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
            return cfg

        def write_cfg(self):
            with open(self.cfg_path, 'w', encoding='utf-8') as f:
                json.dump(self.cfg, f, indent=4)

        def get_cfg(self, key, default=None):
            return self.cfg.get(key, default)

        def set_cfg(self, key, value):
            self.cfg[key] = value
            self.write_cfg()

        def del_cfg(self, key):
            self.cfg.pop(key)
            self.write_cfg()

        def get_all_cfg(self):
            return self.cfg


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
                    setattr(plugin_class, '_temp_dir', os.path.join(getattr(plugin_class, '_data_dir'), 'temp'))
                    os.path.exists(getattr(plugin_class, '_temp_dir')) or os.mkdir(getattr(plugin_class, '_temp_dir'))
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
