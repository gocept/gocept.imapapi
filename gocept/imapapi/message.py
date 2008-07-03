# Copyright (c) 2008 gocept gmbh & co. kg
# See also LICENSE.txt
# $Id$


import email.Header
import gocept.imapapi.interfaces
import zope.interface


class Message(dict):

    zope.interface.implements(gocept.imapapi.interfaces.IMessage)

    __allow_access_to_unprotected_subobjects__ = True

    def __init__(self, name, parent, headers):
        super(Message, self).__init__(headers)
        self.name = name
        self.parent = parent

    def __getitem__(self, key):
        result = u''
        value = super(Message, self).__getitem__(key)
        decoded = email.Header.decode_header(value)
        for text, charset in decoded:
            if charset is None:
                result += text.decode('ascii', 'ignore')
            else:
                result += text.decode(charset, 'ignore')
        return result
