import os


class Environment(object):

    def __init__(self, buildout, name, options):
        self.options = options
        options.update(os.environ)
        options['UID'] = str(os.getuid())
        options['GID'] = str(os.getgid())

    def install(self):
        return []

    def update(self):
        pass
