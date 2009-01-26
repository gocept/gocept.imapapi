# Copyright (c) 2008-2009 gocept gmbh & co. kg
# See also LICENSE.txt
# $Id: account.py 12226 2008-07-01 13:39:31Z thomas $

import UserDict
import email.Parser
import gocept.imapapi.interfaces
import gocept.imapapi.message
import gocept.imapapi.parser
import zope.interface


class Folder(object):

    zope.interface.implements(gocept.imapapi.interfaces.IFolder)

    def __init__(self, name=None, parent=None, separator=None):
        self.name = name
        self.parent = parent
        self._separator = separator

    def __repr__(self):
        repr = super(Folder, self).__repr__()
        return repr.replace('object', "object '%s'" % self.path)

    @property
    def server(self):
        return self.parent.server

    @property
    def depth(self):
        if gocept.imapapi.interfaces.IAccount.providedBy(self.parent):
            return 1
        else:
            return self.parent.depth + 1

    @property
    def separator(self):
        # RfC 3501 requires to always use the same separator as given by the
        # top-level node.
        if self.depth == 1:
            return self._separator
        else:
            return self.parent.separator

    @property
    def path(self):
        if self.depth == 1:
            return self.name
        else:
            return self.parent.path + self.separator + self.name

    @property
    def folders(self):
        return Folders(self)

    @property
    def messages(self):
        return gocept.imapapi.message.Messages(self)

    _message_count_cache = None

    @property
    def message_count(self):
        """Returns the number of messages in the folder.

        The number is cached during the transaction. Since RfC 3501 states
        that the STATUS command should not be used on the currently selected
        mail box, the same value will be set when selecting the folder.

        """
        if self._message_count_cache is None:
            code, data = self.server.status(self.path, "(MESSAGES)")
            assert code == 'OK'
            self._message_count_cache = (
                gocept.imapapi.parser.status(data[0])['MESSAGES'])
        return self._message_count_cache

    def _select(self):
        """Selects the folder as the current folder of the connection.

        Caches the number of messages in the folder. If the folder is already
        selected, this is a no-op.

        """
        if self.server.selected_path != self.path:
            code, data = self.server.select(self.path)
            assert code == 'OK'
            self._message_count_cache = int(data[0])

    _uidvalidity = None

    @property
    def uidvalidity(self):
        """Retrieve the UID validity value of the folder.

        This number must stay the same throughout a session.

        """
        if self._uidvalidity is None:
            code, data = self.server.status(self.path, "(UIDVALIDITY)")
            self._uidvalidity = (
                gocept.imapapi.parser.status(data[0])['UIDVALIDITY'])
        return self._uidvalidity


class Folders(UserDict.DictMixin):
    """A mapping object for accessing folders located in IFolderContainers.
    """

    zope.interface.implements(gocept.imapapi.interfaces.IFolders)

    def __init__(self, container):
        self.container = container

    def keys(self):
        if self.container.depth and self.container.separator is None:
            # We have a non-hierarchical folder.
            return []

        result = []
        if self.container.depth:
            path = self.container.path + self.container.separator
        else:
            path = ''
        code, data = self.container.server.list('', path + '%')
        assert code == 'OK'
        for response in gocept.imapapi.parser.unsplit(data):
            if response is None:
                continue
            flags, sep, name = gocept.imapapi.parser.mailbox_list(response)
            # XXX Looping the separator this way is kind of icky.
            self.separator = sep
            if sep is not None:
                name = name.split(sep)[-1]
            result.append(name)
        result.sort()
        return result

    def __getitem__(self, key):
        if key not in self.keys():
            raise KeyError(key)
        # XXX Part two of the icky separator communication
        return Folder(key, self.container, self.separator)

    def __setitem__(self, key, folder):
        if not isinstance(folder, Folder):
            raise ValueError('Can only store folder objects.')
        if (folder.name is not None or
            folder.parent is not None):
            raise ValueError('Can only assign unattached folder objects.')

        try:
            key = key.encode('ascii')
        except UnicodeDecodeError:
            # XXX Look at modified UTF-7 encoding
            raise ValueError('%r is not a valid folder name.' % name)

        if self.container.depth >= 1:
            path = self.container.path + self.container.separator + key
        else:
            path = key

        code, data = self.container.server.create(path)
        if code == 'NO':
            raise gocept.imapapi.interfaces.IMAPError(
                "Could not create folder '%s': %s" % (path, data[0]))
        assert code == 'OK'

        folder.name = key
        folder.parent = self.container
