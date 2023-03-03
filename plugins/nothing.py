from core import Plugin


class Nothing(Plugin):

    def load(self):
        self.logger.info('loaded')

    def unload(self):
        self.logger.info('unloaded')

    def activate(self):
        self.logger.info('activated')

    def add(self, arg):
        return {'result': int(arg['a']) + int(arg['b'])}
