# Copyright (c) 2008 gocept gmbh & co. kg
# See also LICENSE.txt
# $Id$


import imaplib
import email.Parser

import zope.interface

import gocept.imapapi.interfaces
import gocept.imapapi.message
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

    def folders(self):
        """The folders in this account."""
        result = []
        code, data = self.server.list()
        assert code == 'OK'
        for response in data:
            flags, sep, name = gocept.imapapi.parser.mailbox_list(response)
            name = name.split(sep)
            if len(name) != 1:
                # Ignore all non-root folders
                continue
            name = name[0]
            result.append(gocept.imapapi.folder.Folder(name, self, sep))
        return result
