# Copyright (c) 2008-2009 gocept gmbh & co. kg
# See also LICENSE.txt

import cStringIO
import UserDict
import base64
import email.Header
import email.Message
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
            result += fallback_decode(text, charset)
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


class MIMEHeaders(object):

    def __init__(self, message, part_id):
        self.message = message
        self.part_id = part_id
        self.headers = self.fetch_headers()

    def __getitem__(self, key):
        header = self.headers.get_params(header=key)
        if not header:
            raise KeyError(key)
        return header[0][0]

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def params(self, key):
        header = self.headers.get_params(header=key)
        if not header:
            return {}
        params = {}
        for param, value in header[1:]:
            if isinstance(value, tuple):
                charset, lang, value = value
                if charset:
                    value = value.decode(charset)
            params[param] = value
        return params

    def fetch_headers(self):
        if not self.part_id:
            return email.Message.Message()
        header_lines = _fetch(self.message.server, self.message.parent,
                              self.message.UID,
                              'BODY.PEEK[%s.MIME]' % self.part_id)
        if header_lines != gocept.imapapi.parser.NIL:
            return parser.parsestr(header_lines, True)
        else:
            return email.Message.Message()


class BodyPart(object):

    zope.interface.implements(gocept.imapapi.interfaces.IBodyPart)

    def __init__(self, data, parent, part_number):
        self._data = data
        self._parent = parent
        self.part_number = part_number
        self.mime_headers = MIMEHeaders(self.message, self.part_id)

    @property
    def server(self):
        return self._parent.server

    @property
    def part_id(self):
        if self.part_number is None:
            return None
        prefix = self._parent.part_id
        if prefix is None:
            prefix = ''
        else:
            prefix += '.'
        return '%s%s' % (prefix, self.part_number)

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
        for i, part in enumerate(self._data.get('parts', ())):
            parts.append(BodyPart(part, self, i+1))
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
            if data == gocept.imapapi.parser.NIL:
                raise gocept.imapapi.interfaces.BrokenMIMEPart()
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

    @property
    def estimated_attachments(self):
        major, minor = self['content_type'].split(';', 1)[0].split('/')
        attachments = 0
        if major == 'message':
            # An attached message counts as an attachment itself and
            # additionally contributes its attachments in turn.
            attachments += 1
        if major == 'text':
            # A text part counts as an attachment depending on its
            # content-disposition.
            cd_header = self.mime_headers.get('Content-Disposition', '')
            cd = cd_header.split(';', 1)[0]
            if cd == 'attachment':
                attachments += 1
        elif major in ('multipart', 'message'):
            # Now handle the various multipart sub-types.
            if self.parts:
                if minor == 'alternative':
                    attachments += self.parts[-1].estimated_attachments
                elif minor == 'signed':
                    attachments += self.parts[0].estimated_attachments
                elif minor == 'encrypted':
                    attachments += 1
                else:
                    # Unknown multipart sub-types are treated as
                    # multipart/mixed.
                    attachments += sum(part.estimated_attachments
                                       for part in self.parts)
        else:
            # Any other single-part can only be an attachment.
            attachments += 1
        return attachments


class MessagePart(object):
    """Message that is contained in a body part of type message/rfc822.
    """

    zope.interface.implements(gocept.imapapi.interfaces.IMessage)

    def __init__(self, body):
        self.headers = MessageHeaders(body.message, body['envelope'])
        self.body = body.parts[0]
        self.parent = body

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

    __bodystructure = None
    @property
    def _bodystructure(self):
        if self.__bodystructure is None:
            # We may safely cache the body structure as RfC 3501 asserts that
            # this information must not change for any given message. We can
            # afford to do so since the size of body structure data does not
            # depend on the size of message text or attachments.
            self.__bodystructure = _fetch(
                self.server, self.parent, self.UID, 'BODYSTRUCTURE')
        return self.__bodystructure

    @property
    def body(self):
        return BodyPart(self._bodystructure, self, None)

    @property
    def estimated_attachments(self):
        return self.body.estimated_attachments


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

        # XXX debug #6830
        import pprint
        __traceback_info__ = pprint.pformat(data)

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
        if isinstance(key, slice):
            self._delslice(key)
            return

        # XXX This method should not access the message count cache of its
        # container directly. Ideally, it should not even have to care about
        # the message count; this is what EXPUNGE responses are for.
        message = self[key]
        message.flags.add('\\Deleted')
        self.container._select()
        self.container.server.expunge()
        if self.container._message_count_cache is not None:
            self.container._message_count_cache -= 1

    def __delslice__(self, begin, end):
        self._delslice(slice(begin, end))

    def _delslice(self, slice):
        # XXX This method should not access the message count cache of its
        # container directly. Ideally, it should not even have to care about
        # the message count; this is what EXPUNGE responses are for.
        keys = self.keys()[slice.start:slice.stop:slice.step]
        for key in keys:
            message = self[key]
            message.flags.add('\\Deleted')
        self.container._select()
        self.container.server.expunge()
        if self.container._message_count_cache is not None:
            self.container._message_count_cache -= len(keys)

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

    def filtered(self, sort_by=None, sort_dir='asc',
                 filter_by=None, filter_value=None):
        # XXX make API for sort_by not IMAP-syntax specific.
        sort_criterion = (sort_by or 'ARRIVAL').upper()
        self.container._select()
        if sort_criterion == 'FROM_NAME':
            # we want to sort by *name* and address, but since IMAP SORT only
            # support sorting by address, we need to roll our own.
            uids = self._filtered_by_header(
                'FROM', self.from_name, sort_dir, filter_by, filter_value)
        else:
            uids = self._filtered_by_imap(
                sort_criterion, sort_dir, filter_by, filter_value)
        uids = [self._key(uid) for uid in uids]
        return LazyMessageSequence(uids, self)

    def _filtered_by_imap(self, sort_criterion, sort_dir,
                          filter_by, filter_value):
        if sort_dir == 'desc':
            sort_criterion = 'REVERSE ' + sort_criterion
        code, data = self.container.server.uid(
            'SORT', '(%s)' % sort_criterion, 'UTF-8',
            *self._search_criteria(filter_by, filter_value))
        assert code == 'OK'
        uids = gocept.imapapi.parser.search(data)
        return uids

    def _search_criteria(self, filter_by, filter_value):
        if filter_by is None or filter_value is None or filter_value == '':
            return ('ALL',)

        if isinstance(filter_value, (str, unicode)):
            filter_value = filter_value.replace('\\', '\\\\')
            filter_value = filter_value.replace('"', '\\"')
            filter_value = filter_value.encode('utf-8')

        if filter_by is gocept.imapapi.interfaces.FILTER_SUBJECT:
            return ('SUBJECT', '"%s"' % filter_value)
        elif filter_by is gocept.imapapi.interfaces.FILTER_SENDER:
            return ('HEADER', 'FROM', '"%s"' % filter_value)
        elif filter_by is gocept.imapapi.interfaces.FILTER_SUBJECT_OR_SENDER:
            return ('OR',
                    'SUBJECT', '"%s"' % filter_value,
                    'HEADER', 'FROM', '"%s"' % filter_value)
        elif filter_by is gocept.imapapi.interfaces.FILTER_TO_OR_CC:
            return ('OR',
                    'HEADER', 'TO', '"%s"' % filter_value,
                    'HEADER', 'CC', '"%s"' % filter_value)
        elif filter_by is gocept.imapapi.interfaces.FILTER_SEEN:
            return filter_value and ('SEEN',) or ('UNSEEN',)
        else:
            raise ValueError('Invalid search criterion %r' % filter_by)

    def _filtered_by_header(self, field, key, sort_dir,
                            filter_by, filter_value):
        uids = self._filtered_by_imap(
            'ARRIVAL', 'asc', filter_by, filter_value)
        uids = ','.join(str(uid) for uid in uids)
        code, data = self.container.server.uid(
            'FETCH', uids, '(BODY[HEADER.FIELDS (%s)])' % field)
        assert code == 'OK'
        items = gocept.imapapi.parser.fetch(data, fetch_all=True)
        for item in items:
            lines = item.get('BODY[HEADER.FIELDS (%s)]' % field, '')
            __traceback_info__ = 'BODY[HEADER.FIELDS (%s)]: %r' % (field, lines)
            line = lines.splitlines()[0]
            if line:
                assert line.upper().startswith(field.upper() + ':'), \
                    'Expected %r line, got %r.' % (
                    field, ':' in line and line.split(':')[0]+': xxx' or line)
                value = line.split(':', 1)[1].lstrip()
                item['key'] = key(value)
        result = [item['UID']
                  for item in sorted(items, key=lambda item: item.get('key'))]
        if sort_dir == 'desc':
            result.reverse()
        return result

    def from_name(self, value):
        name, addr = email.Utils.parseaddr(value)
        return (name + addr).lower()

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
        messages.sort(key=lambda x: self.uids.index(x.name))
        return messages

    def __getitem__(self, i):
        return self.messages[self.uids[i]]

    def __len__(self):
        return len(self.uids)


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
        if data is None or data == [None]:
            # None: called without a previous FETCH or STORE
            # [None]: empty FETCH response
            code, data = self.server.uid('FETCH', self.message.UID, 'FLAGS')
            assert code == 'OK'
            __traceback_info__ = 'Server response: %s, %r' % (code, data)
        self.flags = gocept.imapapi.parser.fetch(data)['FLAGS']

    def _store(self, flag, sign):
        self.message.parent._select()
        code, data = self.server.uid(
            'STORE', '%s' % self.message.UID, '%sFLAGS' % sign, '(%s)' % flag)
        assert code == 'OK'
        if sign == '+':
            self.flags.add(flag)
        else:
            self.flags.discard(flag)


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
    __traceback_info__ = 'Server %s:%s, response to FETCH %s %s: %s, %r' % (
        server.host, server.port, msg_uid, data_item_req, code, data)
    data = gocept.imapapi.parser.fetch(data)
    return data[data_item_resp]


def fallback_decode(text, encoding='ascii'):
    try:
        return text.decode(encoding)
    except (TypeError, LookupError, UnicodeDecodeError):
        pass
    try:
        return text.decode('utf-8')
    except UnicodeDecodeError:
        pass
    # XXX We might want to decode('ascii', 'replace') instead:
    return text.decode('iso8859-15')
