# Copyright (c) 2008 gocept gmbh & co. kg
# See also LICENSE.txt
# $Id: account.py 12226 2008-07-01 13:39:31Z thomas $


import email.Parser

import zope.interface

import gocept.imapapi.interfaces
import gocept.imapapi.message


class Folder(object):

    zope.interface.implements(gocept.imapapi.interfaces.IFolder)

    def __init__(self, name, parent, separator):
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

    def folders(self, name=None):
        """The subfolders in this folder."""
        result = []
        path = self.path
        if name:
            path = path + self.separator + name
        code, data = self.server.list(path)
        assert code == 'OK'
        for response in gocept.imapapi.parser.unsplit(data):
            if response is None:
                continue
            flags, sep, name = gocept.imapapi.parser.mailbox_list(response)
            name = name.split(sep)
            if len(name) != self.depth + 1:
                # Ignore all folders that are not direct children.
                continue
            name = name[-1]
            result.append(gocept.imapapi.folder.Folder(
                name, self, sep))
        result.sort(key=lambda folder:folder.name)
        return result

    def messages(self, name=None):
        code, data = self.server.select(self.path)
        count = int(data[0])

        # XXX The UID validity value should be stored on the folder. It must
        # be valid throughout a session.
        code, data = self.server.status(self.path, "(UIDVALIDITY)")
        uidvalidity = gocept.imapapi.parser.uidvalidity(data[0])

        # Step 1: Fetch by various criteria
        fetched_msgs = []
        if name is not None:
            # Variant 1: Fetch by UID
            validity, uid = name.split('-')
            if int(validity) == uidvalidity:
                code, data = self.server.uid('FETCH', '%s' % uid, '(UID RFC822.HEADER)')
                fetched_msgs.append(data)
        else:
            # Variant 2: Fetch by sequence number
            code, data = self.server.status(self.path, "(UIDVALIDITY)")
            for i in xrange(1, count+1):
                code, data = self.server.fetch(str(i), '(UID RFC822.HEADER)')
                fetched_msgs.append(data)

        # Step 2: Process fetched data
        msgs = []
        parser = email.Parser.Parser()
        for data in fetched_msgs:
            uid, headers = gocept.imapapi.parser.message_uid_headers(
                gocept.imapapi.parser.unsplit_one(data))
            name = '%s-%s' % (uidvalidity, uid)
            msg = parser.parsestr(headers, True)
            msgs.append(gocept.imapapi.message.Message(
                name, self, msg))
        return msgs
