# Copyright (c) 2008-2009 gocept gmbh & co. kg
# See also LICENSE.txt

import UserDict
import base64
import email.Header
import email.Parser
import gocept.imapapi.interfaces
import imaplib
import quopri
import time
import zope.interface


parser = email.Parser.Parser()


class MessageHeaders(UserDict.DictMixin):
    """A dictionary that performs RfC 2822 header decoding on access."""

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
                try:
                    result += text.decode(charset, 'replace')
                except LookupError:
                    result += text.decode('ascii', 'replace')
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

    def __contains__(self, key):
        return key in self._data

    @property
    def parts(self):
        parts = []
        for part in self._data.get('parts', ()):
            parts.append(BodyPart(part, self))
        return parts

    def find_all(self, content_type):
        if self['content_type'].split(';')[0] == content_type:
            yield self
        else:
            for child in self.parts:
                for part in child.find_all(content_type):
                    yield part

    def find_one(self, content_type):
        for part in self.find_all(content_type):
            return part

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
            # RfC 3501: The part number of a single non-multipart message is
            # always 1.
            partnumber = '1'
        else:
            partnumber = self['partnumber']

        self.message.parent._select()
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

    def by_cid(self, cid):
        """Return a sub-part by its Content-ID header."""
        if not cid.startswith('<'):
            # Lame protection against recursion
            cid = '<%s>' % cid
        for part in self.parts:
            if cid == part.get('id'):
                return part
            try:
                # Recursive
                return part.by_cid(cid)
            except KeyError:
                pass
        raise KeyError(cid)


class MessagePart(object):
    """Message that is contained in a body part of type message/rfc822.
    """

    zope.interface.implements(gocept.imapapi.interfaces.IMessage)

    def __init__(self, body):
        self.body = body.parts[0]
        body.message.parent._select()
        code, data = body.server.uid(
            'FETCH', '%s' % body.message.UID,
            '(BODY.PEEK[%s.HEADER])' % body['partnumber'])
        uid, headers = gocept.imapapi.parser.message_uid_headers(
            gocept.imapapi.parser.unsplit_one(data))
        msg = parser.parsestr(headers, True)
        self.headers = MessageHeaders(msg)

    @property
    def text(self):
        body.message.parent._select()
        code, data = self.body.server.uid(
            'FETCH', '%s' % self.UID,
            '(BODY[%s.TEXT])' % self.body['partnumber'])
        assert code == 'OK'
        return data[0][1]

    @property
    def raw(self):
        body.message.parent._select()
        code, data = self.body.server.uid(
            'FETCH', '%s' % self.UID,
            '(BODY.PEEK[%s])' % self.body['partnumber'])
        assert code == 'OK'
        return data[0][1]


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
    def flags(self):
        return Flags(self)

    @property
    def text(self):
        self.parent._select()
        code, data = self.server.uid('FETCH', '%s' % self.UID, '(RFC822.TEXT)')
        assert code == 'OK'
        return data[0][1]

    @property
    def raw(self):
        self.parent._select()
        code, data = self.server.uid('FETCH', '%s' % self.UID, '(BODY.PEEK[])')
        assert code == 'OK'
        return data[0][1]

    @property
    def body(self):
        self.parent._select()
        code, data = self.server.uid('FETCH', '%s' % self.UID,
                                     '(BODYSTRUCTURE)')
        assert code == 'OK'
        structure = gocept.imapapi.parser.message_structure(data[0])
        return BodyPart(structure, self)


class Messages(UserDict.DictMixin):
    """A mapping object for accessing messages located in IMessageContainers.
    """

    zope.interface.implements(gocept.imapapi.interfaces.IMessages)

    def __init__(self, container):
        self.container = container

    def __len__(self):
        return self.container.message_count

    def _key(self, uid):
        return '%s-%s' % (self.container.uidvalidity, uid)

    def _fetch_lines(self, msg_set, spec):
        self.container._select()
        try:
            code, data = self.container.server.fetch(msg_set, spec)
        except imaplib.IMAP4.error:
            # Messages might have been deleted (Dovecot).
            return []
        if code == 'NO':
            # Messages might have been deleted (Cyrus).
            return []
        return gocept.imapapi.parser.unsplit(data)

    def keys(self):
        lines = self._fetch_lines('%s:%s' % (1, len(self)), '(UID)')
        uids = (gocept.imapapi.parser.message_uid(line) for line in lines)
        return [self._key(uid) for uid in uids]

    def _make_message(self, line):
        uid, headers = gocept.imapapi.parser.message_uid_headers(line)
        msg = parser.parsestr(headers, True)
        return Message(self._key(uid), self.container, msg)

    def values(self):
        lines = self._fetch_lines(
            '%s:%s' % (1, len(self)), '(UID RFC822.HEADER)')
        return [self._make_message(line) for line in lines]

    def __getitem__(self, key):
        self.container._select()
        uid = self._split_uid(key)
        code, data = self.container.server.uid(
            'FETCH', uid, '(RFC822.HEADER)')
        if data[0] is None:
            raise KeyError(key)
        line = gocept.imapapi.parser.unsplit_one(data)
        return self._make_message(line)

    def __delitem__(self, key):
        # XXX This method should not access the message count cache of its
        # container directly. Ideally, it should not even have to care about
        # the message count; this is what EXPUNGE responses are for.
        message = self[key]
        message.flags.add('\\Deleted')
        self.container._select()
        self.container.server.expunge()
        self.container._message_count_cache -= 1

    def add(self, message):
        # XXX This method should not access the message count cache of its
        # container directly. Ideally, it should not even have to care about
        # the message count; this is what EXISTS responses are for.
        container = self.container
        if isinstance(message, Message):
            message = message.raw
        # XXX Timezone handling!
        container.server.append(
            container.path, '', time.localtime(), message)
        if self.container._message_count_cache is not None:
            self.container._message_count_cache += 1

    def _split_uid(self, key):
        """Parse and verify validity and UID pair.

        The pair must be given as a string in the form of 'validity-UID'.

        """
        validity, uid = key.split('-')
        if int(validity) != self.container.uidvalidity:
            raise KeyError(
                'Invalid UID validity %s for session with validity %s.' %
                (validity, self.container.uidvalidity))
        return uid


def update(func):
    def wrapped(self, *args, **kw):
        if self.flags is None:
            self._update()
        return func(self, *args, **kw)
    return wrapped


class Flags(object):

    def __init__(self, message):
        self.message = message
        self.server = self.message.server
        self.flags = None

    @update
    def __repr__(self):
        return repr(self.flags).replace('set([', 'flags([')

    @update
    def __len__(self):
        return len(self.flags)

    @update
    def __iter__(self):
        return iter(self.flags)

    @update
    def __contains__(self, flag):
        return flag in self.flags

    def add(self, flag):
        self._store(flag, '+')

    def remove(self, flag):
        self._store(flag, '-')

    def _update(self, data=None):
        if data is None:
            code, data = self.server.uid(
                'FETCH', '%s' % self.message.UID, 'FLAGS')
            assert code == 'OK'
        self.flags = gocept.imapapi.parser.message_flags(data)

    def _store(self, flag, sign):
        self.message.parent._select()
        code, data = self.server.uid(
            'STORE', '%s' % self.message.UID, '%sFLAGS' % sign, '(%s)' % flag)
        assert code == 'OK'
        self._update(data)
