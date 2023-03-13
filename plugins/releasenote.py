import json
import os
import time

from fastapi import HTTPException, status

from core import Plugin


class Releasenote(Plugin):
    def __init__(self):
        super().__init__()
        self.release_ctl = None

    def load(self):
        self.release_ctl = self.ConfigUtil(self.data_dir(), 'releases.json', {
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
        title = params.get('title', None)
        version = params.get('version', None)
        content = params.get('content', None)
        if version is None or content is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='invalid params')
        timestamp = int(time.time())
        releases = self.release_ctl.get_cfg('releases')
        releases.append({
            'timestamp': timestamp,
            'title': title,
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
