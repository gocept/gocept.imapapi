# Copyright (c) 2008 gocept gmbh & co. kg
# See also LICENSE.txt
# $Id$


import zope.interface

import gocept.imapapi.interfaces
import gocept.imapapi.folder
import gocept.imapapi.parser
import gocept.imapapi.imap


class Account(object):

    zope.interface.implements(gocept.imapapi.interfaces.IAccount)

    def __init__(self, host, port, user, password):
        self.host = host
        self.port = port
        self.user = user
        self.password = password

        self.server = gocept.imapapi.imap.IMAPConnection(host, port)
        self.server.login(user, password)

    def folders(self, name=None):
        """The folders in this account."""
        result = []
        if name is None:
            name = ''
        code, data = self.server.list(name)
        assert code == 'OK'
        for response in data:
            if response is None:
                continue
            flags, sep, name = gocept.imapapi.parser.mailbox_list(response)
            name = name.split(sep)
            if len(name) != 1:
                # Ignore all non-root folders
                continue
            name = name[0]
            result.append(gocept.imapapi.folder.Folder(name, self, sep))
        result.sort(key=lambda folder:folder.name)
        return result
