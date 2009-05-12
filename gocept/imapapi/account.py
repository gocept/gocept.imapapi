# Copyright (c) 2008-2009 gocept gmbh & co. kg
# See also LICENSE.txt

import zope.interface

import gocept.imapapi
import gocept.imapapi.interfaces
import gocept.imapapi.folder
import gocept.imapapi.imap

import sys
import imaplib
import socket


class Account(object):

    zope.interface.implements(gocept.imapapi.interfaces.IAccount)

    def __init__(self, host, port, user, password, ssl=False):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.ssl = ssl

        try:
            self.server = gocept.imapapi.imap.IMAPConnection(host, port, ssl)
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
