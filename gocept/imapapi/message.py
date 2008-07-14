# Copyright (c) 2008 gocept gmbh & co. kg
# See also LICENSE.txt
# $Id$

import UserDict
import base64
import email.Header
import gocept.imapapi.interfaces
import quopri
import zope.interface


class MessageHeaders(UserDict.DictMixin):
    """A dictionary that performs RFC 2822 header decoding on access."""

    def __init__(self, data):
        self.data = data

    def __getitem__(self, key):
        result = u''
        if not key in self.data:
            raise KeyError(key)
        value = self.data[key]
        decoded = email.Header.decode_header(value)
        for text, charset in decoded:
            if charset is None:
                result += text.decode('ascii', 'replace')
            else:
                result += text.decode(charset, 'replace')
        return result

    def keys(self):
        return self.data.keys()


class BodyPart(object):

    def __init__(self, data, parent):
        self._data = data
        self._parent = parent

    @property
    def server(self):
        return self._parent.server

    @property
    def message(self):
        if gocept.imapapi.interfaces.IMessage.providedBy(self._parent):
            return self._parent
        return self._parent.message

    def get(self, key, default=None):
        return self._data.get(key, default)

    def __getitem__(self, key):
        return self._data[key]

    @property
    def parts(self):
        parts = []
        for part in self._data['parts']:
            parts.append(BodyPart(part, self))
        return parts

    def fetch(self):
        """Fetch the body part's content.

        Decodes any transfer encoding specified by the
        Content-Transfer-Encoding header field.

        """
        # XXX This is icky. This means that on multipart messages we will
        # fetch everything but on non-multipart messages we only fetch the
        # first element. I also tried creating a fake multi-part body but
        # that ends up in an even worse abstraction once you hand it out to
        # the json encoding code.
        if (not self['content_type'].startswith('multipart/') and
            self['partnumber'] == ''):
            # RFC 3501: The part number of a single non-multipart message is
            # always 1.
            partnumber = '1'
        else:
            partnumber = self['partnumber']

        code, data = self.server.select(self.message.parent.path)
        code, data = self.server.uid('FETCH', '%s' % self.message.UID,
                                     '(BODY[%s])' % partnumber)
        # XXX Performance and memory optimisations here, please.
        data = data[0][1]
        transfer_enc = self.get('encoding')
        if transfer_enc == 'quoted-printable':
            data = quopri.decodestring(data)
        elif transfer_enc == 'base64':
            data = base64.b64decode(data)
        return data


class Message(object):

    zope.interface.implements(gocept.imapapi.interfaces.IMessage)

    __allow_access_to_unprotected_subobjects__ = True

    def __init__(self, name, parent, headers):
        self.headers = MessageHeaders(headers)
        self.name = name
        self.parent = parent

    def __repr__(self):
        repr = super(Message, self).__repr__()
        return repr.replace('object', "object '%s/%s'" % (self.parent.path,
                                                          self.name))

    @property
    def server(self):
        return self.parent.server

    @property
    def UID(self):
        return self.name.split('-')[1]

    @property
    def text(self):
        code, data = self.server.select(self.parent.path)
        code, data = self.server.uid('FETCH', '%s' % self.UID, '(RFC822.TEXT)')
        assert code == 'OK'
        return data[0][1]

    @property
    def raw(self):
        code, data = self.server.select(self.parent.path)
        code, data = self.server.uid('FETCH', '%s' % self.UID, '(BODY.PEEK[])')
        assert code == 'OK'
        return data[0][1]

    @property
    def body(self):
        code, data = self.server.select(self.parent.path)
        code, data = self.server.uid('FETCH', '%s' % self.UID,
                                     '(BODYSTRUCTURE)')
        assert code == 'OK'
        structure = gocept.imapapi.parser.message_structure(data[0])
        return BodyPart(structure, self)
