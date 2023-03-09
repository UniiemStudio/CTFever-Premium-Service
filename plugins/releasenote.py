import json
import os
import time

from fastapi import HTTPException, status

from core import Plugin


class CfgUtil:
    def __init__(self, data_dir: str, cfg_name: str = 'config.json', default_cfg=None):
        self.default_cfg = default_cfg
        if self.default_cfg is None:
            self.default_cfg = {}
        self.cfg_path = os.path.join(data_dir, cfg_name)
        self.cfg = self.read_cfg()

    def read_cfg(self):
        if not os.path.exists(self.cfg_path):
            with open(self.cfg_path, 'w') as f:
                f.write(json.dumps(self.default_cfg))
        with open(self.cfg_path, 'r') as f:
            cfg = json.load(f)
        return cfg

    def write_cfg(self):
        with open(self.cfg_path, 'w') as f:
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


class Releasenote(Plugin):
    def __init__(self):
        super().__init__()
        self.release_ctl = None

    def load(self):
        self.release_ctl = CfgUtil(self.data_dir(), 'releases.json', {
            'latest': 1678496400,
            'releases': [
                {
                    'timestamp': 1678496400,
                    'version': '2.0.0',
                    'content': 'Initial release'
                }
            ]
        })

    def unload(self):
        pass

    def activate(self):
        super().activate()

    def releases(self):
        full_releases = self.release_ctl.get_all_cfg()
        full_releases['releases'] = sorted(full_releases['releases'], key=lambda r: r['timestamp'], reverse=True)
        return full_releases

    def releases_behind(self, params):
        releases = self.release_ctl.get_cfg('releases')
        return sorted(
            [release for release in releases if release['timestamp'] > int(params['timestamp'])],
            key=lambda r: r['timestamp'], reverse=True
        )

    def push_release(self, params):
        version = params.get('version', None)
        content = params.get('content', None)
        if version is None or content is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='invalid params')
        timestamp = int(time.time())
        releases = self.release_ctl.get_cfg('releases')
        releases.append({
            'timestamp': timestamp,
            'version': version,
            'content': content
        })
        self.release_ctl.set_cfg('releases', releases)
        self.release_ctl.set_cfg('latest', timestamp)
        return 'ok'

    def latest_release(self):
        latest_timestamp = self.release_ctl.get_cfg('latest', None)
        if latest_timestamp is None:
            return None
        releases = self.release_ctl.get_cfg('releases', [])
        for release in releases:
            if release['timestamp'] == latest_timestamp:
                return release
        return None
