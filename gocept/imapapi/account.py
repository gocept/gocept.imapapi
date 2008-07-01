# Copyright (c) 2008 gocept gmbh & co. kg
# See also LICENSE.txt
# $Id$


import imaplib
import email.Parser

import zope.interface

import Acquisition

import gocept.imapapi.interfaces
import gocept.imapapi.message


class Account(Acquisition.Explicit):

    zope.interface.implements(gocept.imapapi.interfaces.IAccount)

    def __init__(self, host, port, user, password):
        self.host = host
        self.port = port
        self.user = user
        self.password = password

        self.server = imaplib.IMAP4(host, port)
        self.server.login(user, password)

    def get_messages(self):
        code, data = self.server.select('INBOX')
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
