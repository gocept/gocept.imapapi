# Copyright (c) 2008 gocept gmbh & co. kg
# See also LICENSE.txt
# $Id$


import zope.interface

import gocept.imapapi
import gocept.imapapi.interfaces
import gocept.imapapi.folder
import gocept.imapapi.parser
import gocept.imapapi.imap

import sys
import imaplib
import socket


class Account(object):

    zope.interface.implements(gocept.imapapi.interfaces.IAccount)

    depth = 0
    path = ''

    def __init__(self, host, port, user, password):
        self.host = host
        self.port = port
        self.user = user
        self.password = password

        try:
            self.server = gocept.imapapi.imap.IMAPConnection(host, port)
        except socket.gaierror:
            raise gocept.imapapi.IMAPServerError(sys.exc_info()[1])
        except socket.error:
            raise gocept.imapapi.IMAPServerError(sys.exc_info()[1])

        try:
            self.server.login(user, password)
        except imaplib.IMAP4.error:
            raise gocept.imapapi.IMAPConnectionError(sys.exc_info()[1])

    @property
    def folders(self):
        return gocept.imapapi.folder.Folders(self)
