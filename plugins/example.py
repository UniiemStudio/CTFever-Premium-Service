import asyncio
import time

from core import Plugin


class Example(Plugin):
    def load(self):
        self.logger.info('loaded')

    def unload(self):
        self.logger.info('unloaded')

    def activate(self):
        self.logger.info('activated')

    def deactivate(self):
        self.logger.info('deactivated')

    async def test(self):
        await asyncio.sleep(5)
        return {'message': 'called test method'}

    async def echo(self, message: str):
        return {'message': message}
