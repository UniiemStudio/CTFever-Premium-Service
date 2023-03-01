from core import Plugin


class Nothing(Plugin):

    def unload(self):
        self.logger.info('unloaded')

    def activate(self):
        self.logger.info('activated')
