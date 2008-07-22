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

    depth = 0
    path = ''

    def __init__(self, host, port, user, password):
        self.host = host
        self.port = port
        self.user = user
        self.password = password

        self.server = gocept.imapapi.imap.IMAPConnection(host, port)
        self.server.login(user, password)

    @property
    def folders(self):
        return gocept.imapapi.folder.Folders(self)
