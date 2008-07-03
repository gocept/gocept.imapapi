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

    def server(self):
        if callable(self.parent.server):
            return self.parent.server()
        else:
            return self.parent.server

    def depth(self):
        if gocept.imapapi.interfaces.IAccount.providedBy(self.parent):
            return 1
        else:
            return self.parent.depth() + 1

    def separator(self):
        # RFC3501 requires to always use the same separator as given by the
        # top-level node.
        if self.depth() == 1:
            return self._separator
        else:
            return self.parent.separator()

    def path(self):
        if self.depth() == 1:
            return self.name
        else:
            return self.parent.path() + self.separator() + self.name

    def folders(self):
        """The subfolders in this folder."""
        result = []
        code, data = self.server().list(self.path())
        assert code == 'OK'
        for response in data:
            flags, sep, name = gocept.imapapi.parser.mailbox_list(response)
            name = name.split(sep)
            if len(name) != self.depth() + 1:
                # Ignore all folders that are not direct children.
                continue
            name = name[-1]
            result.append(gocept.imapapi.folder.Folder(
                name, self, sep))
        return result

    def messages(self):
        code, data = self.server().select(self.path())
        count = int(data[0])
        code, data = self.server().status(self.path(), "(UIDVALIDITY)")
        # XXX The UID validity value should be stores on the folder. It must
        # be valid throughout a session.
        uidvalidity = gocept.imapapi.parser.uidvalidity(data[0])
        msgs = []
        parser = email.Parser.Parser()
        for i in xrange(1, count+1):
            code, data = self.server().fetch(str(i), '(UID RFC822.HEADER)')
            msg_data = data[0]
            uid = gocept.imapapi.parser.message_uid_other(msg_data[0])
            name = '%s-%s' % (uidvalidity, uid)
            msg_str = msg_data[1]
            msg = parser.parsestr(msg_str, True)
            msgs.append(gocept.imapapi.message.Message(
                name, self, msg).__of__(self))
        return msgs
