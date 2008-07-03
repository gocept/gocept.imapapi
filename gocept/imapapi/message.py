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

    def server(self):
        return self.parent.server()

    @property
    def UID(self):
        return self.name.split('-')[1]

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

    def text(self):
        code, data = self.server().select(self.parent.path())
        code, data = self.server().uid('FETCH', '%s' % self.UID, '(RFC822.TEXT)')
        assert code == 'OK'
        return data[0][1]

    def raw(self):
        code, data = self.server().select(self.parent.path())
        code, data = self.server().uid('FETCH', '%s' % self.UID, '(BODY.PEEK[])')
        assert code == 'OK'
        return data[0][1]
