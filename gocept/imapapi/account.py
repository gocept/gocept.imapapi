# Copyright (c) 2008 gocept gmbh & co. kg
# See also LICENSE.txt
# $Id$


import imaplib
import email.Parser

import zope.interface

import gocept.imapapi.interfaces


class Account(object):

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
            msgs.append(parser.parsestr(msg_str, True))
        return msgs
