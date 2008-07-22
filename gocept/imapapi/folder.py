# Copyright (c) 2008 gocept gmbh & co. kg
# See also LICENSE.txt
# $Id: account.py 12226 2008-07-01 13:39:31Z thomas $

import UserDict
import email.Parser

import zope.interface

import gocept.imapapi.interfaces
import gocept.imapapi.message



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


class Folders(UserDict.DictMixin):
    """A mapping object for accessing folders located in IFolderContainers.
    """

    zope.interface.implements(gocept.imapapi.interfaces.IFolders)

    def __init__(self, container):
        self.container = container

    def keys(self):
        result = []
        path = self.container.path
        code, data = self.container.server.list(path)
        assert code == 'OK'
        for response in gocept.imapapi.parser.unsplit(data):
            if response is None:
                continue
            flags, sep, name = gocept.imapapi.parser.mailbox_list(response)
            # XXX Looping the separator this way is kind of icky.
            self.separator = sep
            name = name.split(sep)
            if len(name) != self.container.depth + 1:
                # Ignore all folders that are not direct children.
                continue
            name = name[-1]
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
