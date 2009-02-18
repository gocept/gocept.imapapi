# Copyright (c) 2008-2009 gocept gmbh & co. kg
# See also LICENSE.txt

import cStringIO
import UserDict
import base64
import email.Header
import email.Parser
import gocept.imapapi.interfaces
import gocept.imapapi.parser
import imaplib
import itertools
import quopri
import tempfile
import time
import zope.interface

parser = email.Parser.Parser()


class MessageHeaders(UserDict.DictMixin):
    """A dictionary that performs RfC 2822 header decoding on access."""

    def __init__(self, message, envelope):
        self.message = message
        self.envelope = envelope
        self.headers = None

    def __getitem__(self, key):
        # try to get along without fetching the headers
        try:
            value = self.envelope[key.lower()]
        except KeyError:
            self.fetch_headers()
            value = self.headers[key]
        if value is None:
            return u''
        result = u''
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
        self.fetch_headers()
        return self.headers.keys()

    def fetch_headers(self):
        if self.headers is not None:
            return
        header_lines = _fetch(self.message.server, self.message.parent,
                              self.message.UID, 'BODY.PEEK[HEADER]')
        self.headers = parser.parsestr(header_lines, True)


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
        temp = cStringIO.StringIO()
        self.fetch_file(temp)
        return temp.getvalue()

    def fetch_file(self, f):
        """Fetch the body part into a file-like object."""
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

        encoding = self.get('encoding')
        if encoding in ['base64', 'quoted-printable']:
            # XXX Make StringIO first, swap to temporary file on a size threshold.
            encoded = tempfile.NamedTemporaryFile()
        else:
            encoded = f

        for chunk_no in itertools.count():
            data = _fetch(self.server, self.message.parent, self.message.UID,
                          'BODY[%s]' % partnumber, chunk_no)
            if data == '':
                break
            encoded.write(data)

        encoded.seek(0)
        if encoding == 'base64':
            base64.decode(encoded, f)
        elif encoding == 'quoted-printable':
            quopri.decode(encoded, f)
        f.seek(0)

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
        self.headers = MessageHeaders(body.message, body['envelope'])
        self.body = body.parts[0]

    @property
    def text(self):
        return _fetch(self.body.server, self.body.message.parent, self.UID,
                      'BODY[%s.TEXT]' % self.body['partnumber'])

    @property
    def raw(self):
        return _fetch(self.body.server, self.body.message.parent, self.UID,
                      'BODY.PEEK[%s]' % self.body['partnumber'])


class Message(object):

    zope.interface.implements(gocept.imapapi.interfaces.IMessage)

    # XXX WTF?
    __allow_access_to_unprotected_subobjects__ = True

    def __init__(self, name, parent, envelope, flags):
        self.headers = MessageHeaders(self, envelope)
        self.name = name
        self.parent = parent
        self.flags = Flags(self, flags)

    def __repr__(self):
        repr = super(Message, self).__repr__()
        return repr.replace(
            'object', 'object %r' % '/'.join((self.parent.path, self.name)))

    @property
    def server(self):
        return self.parent.server

    @property
    def UID(self):
        return self.name.split('-')[1]

    @property
    def text(self):
        return _fetch(self.server, self.parent, self.UID, 'BODY[TEXT]')

    @property
    def raw(self):
        return _fetch(self.server, self.parent, self.UID, 'BODY.PEEK[]')

    _bodystructure = None

    @property
    def body(self):
        if self._bodystructure is None:
            # We may safely cache the body structure as RfC 3501 asserts that
            # this information must not change for any particular message. We
            # can afford to do so since the size of body structure data does
            # not depend on the size of message text or attachedments.
            self._bodystructure = _fetch(
                self.server, self.parent, self.UID, 'BODYSTRUCTURE')
        return BodyPart(self._bodystructure, self)


class Messages(UserDict.DictMixin):
    """A mapping object for accessing messages located in IMessageContainers.
    """

    zope.interface.implements(gocept.imapapi.interfaces.IMessages)

    def __init__(self, container):
        self.container = container

    def __repr__(self):
        return '<%s messages of %r>' % (len(self), self.container)

    def __len__(self):
        return self.container.message_count

    def _key(self, uid):
        return '%s-%s' % (self.container.uidvalidity, uid)

    def _fetch_lines(self, msg_set, spec, uid=False):
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
        uids = (gocept.imapapi.parser.fetch(line)['UID'] for line in lines)
        return [self._key(uid) for uid in uids]

    def _make_message(self, line):
        data = gocept.imapapi.parser.fetch(line)
        return Message(
            self._key(data['UID']), self.container, data['ENVELOPE'],
            data['FLAGS'])

    def values(self):
        lines = self._fetch_lines(
            '%s:%s' % (1, len(self)), '(UID ENVELOPE FLAGS)')
        return [self._make_message(line) for line in lines]

    def by_uids(self, uids):
        # XXX naming of this method sucks :/
        uids = ','.join(self._split_uid(uid) for uid in uids)
        self.container._select()
        try:
            code, data = self.container.server.UID(
                'FETCH', uids, '(UID ENVELOPE FLAGS)')
        except imaplib.IMAP4.error:
            # Messages might have been deleted (Dovecot).
            return []
        if code == 'NO':
            # Messages might have been deleted (Cyrus).
            return []
        return [self._make_message(line)
                for line in gocept.imapapi.parser.unsplit(data)]

    def __getitem__(self, key):
        self.container._select()
        uid = self._split_uid(key)
        code, data = self.container.server.uid('FETCH', uid, '(ENVELOPE FLAGS)')
        if data[0] is None:
            raise KeyError(key)
        return self._make_message(data)

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
            container.encoded_path, '', time.localtime(), message)
        if self.container._message_count_cache is not None:
            self.container._message_count_cache += 1

    def filtered(self, sort_by, sort_dir='asc'):
        # XXX make API for sort_by not IMAP-syntax specific.
        sort_criterion = sort_by.upper()
        if sort_dir == 'desc':
            sort_criterion = 'REVERSE ' + sort_criterion
        self.container._select()
        code, data = self.container.server.uid(
            'SORT', '(%s)' % sort_criterion, 'UTF-8', 'ALL')
        assert code == 'OK'
        uids = gocept.imapapi.parser.search(data)
        uids = [self._key(uid) for uid in uids]
        return LazyMessageSequence(uids, self)

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


class LazyMessageSequence(object):

    def __init__(self, uids, messages):
        self.uids = uids
        self.messages = messages

    def __getslice__(self, i, j):
        messages = self.messages.by_uids(self.uids[i:j])
        messages.sort(key=lambda x:self.uids.index(x.name))
        return messages

    def __getitem__(self, i):
        return self.messages[self.uids[i]]


def update(func):
    def wrapped(self, *args, **kw):
        if self.flags is None:
            self._update()
        return func(self, *args, **kw)
    return wrapped


class Flags(object):

    def __init__(self, message, flags=None):
        self.message = message
        self.server = self.message.server
        self.flags = flags

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
            code, data = self.server.uid('FETCH', self.message.UID, 'FLAGS')
            assert code == 'OK'
        self.flags = gocept.imapapi.parser.fetch(data)['FLAGS']

    def _store(self, flag, sign):
        self.message.parent._select()
        code, data = self.server.uid(
            'STORE', '%s' % self.message.UID, '%sFLAGS' % sign, '(%s)' % flag)
        assert code == 'OK'
        self._update(data)


def _fetch(server, mailbox, msg_uid, data_item, chunk_no=None):
    # XXX This should definitely be a method of some appropriate class, but
    # such a refactoring will probably only make sense after messages and body
    # parts have been unified.
    mailbox._select()

    data_item_req = data_item
    data_item_resp = data_item.replace('.PEEK', '')
    if chunk_no is not None:
        buffer_size = 1<<24 # 8 MB chunks
        offset = chunk_no * buffer_size
        data_item_req += '<%i.%i>' % (offset, buffer_size)
        data_item_resp += '<%i>' % offset

    data_item_req = '(%s)' % data_item_req
    code, data = server.uid('FETCH', msg_uid, data_item_req)
    assert code == 'OK'
    data = gocept.imapapi.parser.fetch(data)
    return data[data_item_resp]
