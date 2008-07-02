# Copyright (c) 2008 gocept gmbh & co. kg
# See also LICENSE.txt
# $Id: account.py 12226 2008-07-01 13:39:31Z thomas $


import imaplib
import email.Parser

import zope.interface

import Acquisition

import gocept.imapapi.interfaces
import gocept.imapapi.message


class Folder(Acquisition.Explicit):

    zope.interface.implements(gocept.imapapi.interfaces.IFolder)

    def __init__(self, name, parent, separator):
        self.name = name
        self.parent = parent
        self._separator = separator

    def __repr__(self):
        repr = super(Folder, self).__repr__()
        return repr.replace('object', "object '%s'" % self.name)

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
        # RFC3501 requires to always use the same separator as given by the
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
        """The subfolders in this folder."""
        result = []
        code, data = self.server.list(self.path)
        assert code == 'OK'
        for response in data:
            flags, sep, name = gocept.imapapi.parser.mailbox_list(response)
            name = name.split(sep)
            if len(name) != self.depth + 1:
                # Ignore all folders that are not direct children.
                continue
            name = name[-1]
            result.append(gocept.imapapi.folder.Folder(
                name, self, sep))
        return result

    @property
    def messages(self):
        code, data = self.server.select(self.path)
        count = int(data[0])
        msgs = []
        parser = email.Parser.Parser()
        for i in xrange(1, count+1):
            code, data = self.server.fetch(str(i), '(RFC822)')
            msg_data = data[0]
            msg_str = msg_data[1]
            msg = parser.parsestr(msg_str, True)
            msgs.append(gocept.imapapi.message.Message(msg).__of__(self))
        return msgs
