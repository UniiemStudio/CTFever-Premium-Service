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

    def test(self):
        self.logger.info('🔌 Test Example')
