# vim:fileencoding=utf-8
# Copyright (c) 2008-2009 gocept gmbh & co. kg
# See also LICENSE.txt
"""Parsing IMAP responses."""

def iterate_pairs(iterable):
    iterable = iter(iterable)
    while True:
        yield iterable.next(), iterable.next()


def dict_from_sequence(sequence):
    result = {}
    for key, value in iterate_pairs(sequence):
        assert type(key) in (Atom, AttributeSpec)
        result[str(key)] = value
    return result


def unsplit(items):
    """Restore the raw IMAP response from what imaplib server commands return.

    """
    if items == [None]:
        return
    line = ''
    for item in items:
        if type(item) is tuple:
            line += '\r\n'.join(item)
        else:
            yield line + item
            line = ''
    assert not line


def mailbox_list(line):
    r"""Parse an IMAP `mailbox_list` response.

    Returns a tuple: (flags, separator, name)

    Currently this is only intended to handle responses as dovecot returns
    them:

    >>> mailbox_list('(\\Noselect \\HasChildren) "/" INBOX')
    ([<IMAP flag \Noselect>, <IMAP flag \HasChildren>], '/', 'INBOX')
    >>> mailbox_list('(\\NoInferiors \\UnMarked) "/" "INBOX/Baz/qux"')
    ([<IMAP flag \NoInferiors>, <IMAP flag \UnMarked>], '/', 'INBOX/Baz/qux')

    """
    flags, sep, name = parse(line)
    if sep == NIL:
        sep = None
    return flags, sep, mailbox(name)


def status(line):
    """Parse an IMAP `status` response.
    """
    foldername, response = parse(line)
    status = {}
    for key, value in iterate_pairs(response):
        status[str(key)] = number(value)
    return status


def fetch(line, fetch_all=False):
    """Parse an IMAP `fetch` response.
    """
    if isinstance(line, basestring):
        lines = iter([line])
    else:
        lines = unsplit(line)
    if fetch_all:
        return [fetch_one(line) for line in lines]
    else:
        return fetch_one(lines.next())


def fetch_one(line):
    msg_number, response = parse(line)
    data = dict_from_sequence(response)
    if 'UID' in data:
        data['UID'] = number(data['UID'])
    if 'ENVELOPE' in data:
        data['ENVELOPE'] = _parse_envelope(data['ENVELOPE'])
    if 'BODYSTRUCTURE' in data:
        data['BODYSTRUCTURE'] = _parse_structure(data['BODYSTRUCTURE'], '')
    if 'FLAGS' in data:
        data['FLAGS'] = set(str(flag) for flag in data['FLAGS'])
    return data


def search(line):
    """Parse an IMAP `search` (or `sort`) response.

    >>> search(['12 14',])
    [12, 14]

    """
    line = unsplit(line).next()
    return [number(x) for x in parse(line)]


def _parse_envelope(envelope):
    envelope = dict(zip(['date', 'subject', 'from', 'sender', 'reply-to',
                         'to', 'cc', 'bcc', 'in-reply-to', 'message-id'],
                        envelope))
    for key, value in envelope.iteritems():
        if value == NIL:
            envelope[key] = u''
        elif isinstance(value, str):
            pass
        elif isinstance(value, list):
            # XXX handle RfC2822-style address groups
            addresses = []
            for item in value:
                name, path, mailbox, host = item
                if name == NIL:
                    addresses.append('%s@%s' % (mailbox, host))
                else:
                    addresses.append('%s <%s@%s>' % (name, mailbox, host))
            envelope[key] = ', '.join(addresses)
    return envelope


def _parse_structure(structure, path):
    if structure[:2] == ['message', 'rfc822']:
        return _parse_message_rfc822(structure, path)
    elif isinstance(structure[0], str):
        return _parse_nonmultipart(structure, path)
    else:
        return _parse_multipart(structure, path)


def _parse_multipart(element, path):
    data = {}
    data['parts'] = []

    if path:
        sub_path_prefix = path + '.'
    else:
        sub_path_prefix = path

    sub_number = 0
    while True:
        subelement = element.pop(0)
        if isinstance(subelement, str):
            # End of structure list.
            break
        sub_number += 1
        data['parts'].append(_parse_structure(subelement, sub_path_prefix + str(sub_number)))

    data['content_type'] = 'multipart/%s' % subelement.lower()
    if element:
        data['parameters'] = {}
        for key, value in iterate_pairs(element.pop(0)):
            data['parameters'][key.lower()] = value
    data['partnumber'] = path
    return data

def _parse_nonmultipart(element, path):
    data = {}
    data['content_type'] = '%s/%s' % (element[0].lower(), element[1].lower())
    data['parameters'] = {}
    if isinstance(element[2], list):
        for key, value in iterate_pairs(element[2]):
            data['parameters'][key.lower()] = value
    data['id'] = nstring(element[3])
    data['description'] = nstring(element[4])
    data['encoding'] = element[5].lower()
    data['size'] = number(element[6])
    data['partnumber'] = path
    return data

def _parse_message_rfc822(element, path):
    data = _parse_nonmultipart(element, path)
    data['envelope'] = _parse_envelope(element[7])
    data['parts'] = [_parse_structure(element[8], path)]
    return data


ATOM_CHARS = [chr(i) for i in xrange(32, 256) if chr(i) not in r'(){%*"\ ]']


class ParseError(Exception):
    def __init__(self, msg, data):
        Exception.__init__(self, "%s in '%s' at index %s." %
                           (msg, data.string, data.index))


class LookAheadStringIter(object):
    """String iterator that allows looking one character ahead.

    >>> i = LookAheadStringIter('abxxxcd')
    >>> i.ahead
    'a'
    >>> i.next()
    'a'
    >>> i.ahead
    'b'
    >>> i.next()
    'b'
    >>> i.read(3)
    'xxx'
    >>> i.ahead
    'c'
    >>> i.next()
    'c'
    >>> i.ahead
    'd'
    >>> i.next()
    'd'
    >>> i.ahead
    >>> i.next()
    Traceback (most recent call last):
    StopIteration
    >>> i.read()
    ''
    >>> i.next()
    Traceback (most recent call last):
    StopIteration
    """

    index = 0

    def __init__(self, string):
        self.string = string

    @property
    def ahead(self):
        if self.string is not None:
            try:
                return self.string[self.index]
            except IndexError:
                pass

    def next(self):
        try:
            result = self.string[self.index]
        except IndexError:
            raise StopIteration
        self.index += 1
        return result

    def read(self, count=None):
        if count is None:
            result = self.string[self.index:]
            self.index = len(self.string)
        else:
            result = self.string[self.index:self.index+count]
            self.index += count
        return result

    def __iter__(self):
        return self

_ = LookAheadStringIter


class Atom(object):
    """An IMAP atom.

    Atoms do not know about interpretation of NIL as None and integer literals
    as numbers. Since that is context dependent, these things belong in the
    code calling the parser.

    >>> repr(Atom('foo'))
    '<IMAP atom foo>'

    >>> str(Atom('foo'))
    'foo'

    >>> Atom('NIL')
    <IMAP atom NIL>

    >>> Atom('123')
    <IMAP atom 123>

    """

    def __init__(self, value):
        self.value = value

    def __eq__(self, other):
        """Test for equality of two atoms.

        >>> Atom('foo') == Atom('bar')
        False

        >>> Atom('foo') == 'foo'
        False

        >>> 'foo' == Atom('foo')
        False

        >>> Atom('foo') == Atom('foo')
        True

        """
        return type(self) is type(other) and self.value == other.value

    def __ne__(self, other):
        """Test for inequality of two atoms.

        >>> Atom('foo') != Atom('bar')
        True

        >>> Atom('foo') != 'foo'
        True

        >>> 'foo' != Atom('foo')
        True

        >>> Atom('foo') != Atom('foo')
        False

        """
        return not self.__eq__(other)

    def __repr__(self):
        return "<IMAP atom %s>" % self.value

    def __str__(self):
        return self.value


class Flag(Atom):
    """An IMAP flag.

    >>> repr(Flag('foo'))
    '<IMAP flag \\\\foo>'

    >>> str(Flag('foo'))
    '\\\\foo'

    """

    def __repr__(self):
        return "<IMAP flag \\%s>" % self.value

    def __str__(self):
        return '\\' + self.value


class AttributeSpec(object):
    """A message attribute specifier: UID, BODY[HEADER.FIELDS (FROM)] etc.
    """

    def __init__(self, primary, msgtext=None, header_list=None, range=None):
        self.primary = primary
        self.msgtext = msgtext
        self.header_list = header_list
        self.range = range

    def __repr__(self):
        return '<AttributeSpec %s>' % self

    def __str__(self):
        result = str(self.primary)
        if self.msgtext is not None:
            if self.header_list is None:
                result += '[%s]' % self.msgtext
            else:
                result += '[%s (%s)]' % (
                    self.msgtext,
                    ' '.join(str(atom) for atom in self.header_list))
        if self.range is not None:
            result += self.range.value
        return result


def read_quoted(data):
    """Read a quoted string from an IMAP response.

    >>> read_quoted(_('"asdf"'))
    'asdf'

    >>> read_quoted(_('"asdf\\\\" " "foo"'))
    'asdf" '

    """
    assert data.next() == '"'
    result = ''
    for c in data:
        if c == '"':
            break
        if c == '\\' and data.ahead in ('"', '\\'):
            c = data.next()
        result += c
    else:
        raise ParseError('Unexpected end of quoted string', data)
    return result


def read_literal(data):
    r"""Read a literal string from an IMAP response.

    >>> read_literal(_('{4}\r\nasdf'))
    'asdf'

    >>> read_literal(_('{4}\r\na\\s\x1adf'))
    'a\\s\x1a'

    >>> read_literal(_('{0}\r\n'))
    ''

    """
    assert data.next() == '{'
    count = ''
    for c in data:
        if c == '}':
            break
        count += c
    if not (data.ahead and data.next() == '\r' and
            data.ahead and data.next() == '\n'):
        raise ParseError('Syntax error in literal string', data)
    try:
        count = int(count)
    except ValueError:
        raise ParseError(
            'Non-integer token for length of literal string', data)

    result = data.read(count)
    if len(result) < count:
        raise ParseError('Unexpected end of literal string', data)
    return result


def read_list(data):
    """Read a parenthesized list from an IMAP response.

    >>> read_list(_('(foo "bar")'))
    [<IMAP atom foo>, 'bar']

    >>> read_list(_('(foo "bar" (baz)) qux'))
    [<IMAP atom foo>, 'bar', [<IMAP atom baz>]]

    """
    assert data.next() == '('
    result = list(parse_recursive(data))
    if not data.ahead or data.next() != ')':
        raise ParseError('Unexpected end of list', data)
    return result


def read_atom(data):
    """Read an atom or attribute specification from an IMAP response.

    Like atoms, this internal function of the parser does not care about NIL
    and integer literals.

    >>> read_atom(_('foo'))
    <IMAP atom foo>

    >>> read_atom(_('bar baz'))
    <IMAP atom bar>

    >>> read_atom(_('NIL'))
    <IMAP atom NIL>

    >>> read_atom(_('123'))
    <IMAP atom 123>

    >>> read_atom(_('BODY[]'))
    <AttributeSpec BODY[]>

    >>> read_atom(_('BODY[HEADER]'))
    <AttributeSpec BODY[HEADER]>

    >>> read_atom(_('BODY[HEADER.FIELDS (FROM)]'))
    <AttributeSpec BODY[HEADER.FIELDS (FROM)]>

    >>> read_atom(_('BODY[HEADER.FIELDS (FROM)]<0>'))
    <AttributeSpec BODY[HEADER.FIELDS (FROM)]<0>>

    """
    assert data.ahead in ATOM_CHARS
    result = ''
    while data.ahead in ATOM_CHARS:
        c = data.next()
        if c == '[':
            break
        else:
            result += c
    else:
        return Atom(result)

    if data.ahead == ']':
        msgtext = ''
    else:
        msgtext = read_atom(data)
    if data.ahead == ' ':
        data.next()
        header_list = read_list(data)
    else:
        header_list = None
    if data.ahead != ']':
        raise ParseError('Unexpected end of header list', data)
    data.next()
    if data.ahead == '<':
        range = read_atom(data)
    else:
        range = None
    return AttributeSpec(result, msgtext, header_list, range)


def read_flag(data):
    """Read a flag from an IMAP response.

    >>> read_flag(_('\\\\Flag'))
    <IMAP flag \\Flag>

    """
    assert data.next() == '\\'
    return Flag(read_atom(data).value)


def parse_recursive(data):
    """Parse an IMAP response until the end of the current nested list.

    This loop is designed in such a way that the read_* functions always
    operate on expressions that include all delimiting characters such as
    quotes, braces and parentheses, and always consume them entirely.

    """
    while True:
        c = data.ahead
        if c == '"':
            yield read_quoted(data)
        elif c == '{':
            yield read_literal(data)
        elif c == '(':
            yield read_list(data)
        elif c == '\\':
            yield read_flag(data)
        elif c in ATOM_CHARS:
            yield read_atom(data)

        c = data.ahead
        if c == ' ':
            data.next()
        elif c in (')', None):
            break
        elif c == '(':
            continue
        else:
            raise ParseError('Syntax error %s' % c, data)


def parse(data):
    r"""Parse an IMAP response with no regard to numerals and NIL.

    >>> parse('')
    []

    >>> parse('foo "bar"')
    [<IMAP atom foo>, 'bar']

    >>> parse('(\\Noselect \\Marked) "/" INBOX/Foo/bar')
    [[<IMAP flag \Noselect>, <IMAP flag \Marked>], '/',
     <IMAP atom INBOX/Foo/bar>]

    >>> parse('''(UID 17 RFC822 {58}\r\n\
    ... From: foo@example.com
    ... Subject: Test
    ...
    ... This is a test mail.
    ...  FLAGS (\\Deleted))''')
    [[<IMAP atom UID>, <IMAP atom 17>, <IMAP atom RFC822>,
     'From: foo@example.com\nSubject: Test\n\nThis is a test mail.\n',
     <IMAP atom FLAGS>, [<IMAP flag \Deleted>]]]

    >>> parse(r'(BODYSTRUCTURE ("TEXT" "PLAIN")("TEXT" "HTML"))')
    [[<IMAP atom BODYSTRUCTURE>, ['TEXT', 'PLAIN'], ['TEXT', 'HTML']]]
    >>> parse(r'(BODYSTRUCTURE ("TEXT" "PLAIN") ("TEXT" "HTML"))')
    [[<IMAP atom BODYSTRUCTURE>, ['TEXT', 'PLAIN'], ['TEXT', 'HTML']]]

    """
    data = LookAheadStringIter(data)
    result = list(parse_recursive(data))
    if data.ahead:
        raise ParseError('Inconsistent nesting of lists', data)
    return result


def astring(value):
    """Interpret a parsed value as an astring.

    An astring is a string that is either represented as a string literal or
    as an atom. It cannot be non-existent.

    >>> astring('foo')
    'foo'

    >>> astring(Atom('bar'))
    'bar'

    >>> astring(Atom('NIL'))
    'NIL'

    >>> astring(['foo', 'bar'])
    Traceback (most recent call last):
    ValueError: ['foo', 'bar'] cannot be read as an astring.

    """
    if isinstance(value, str):
        return value
    elif isinstance(value, Atom):
        return value.value
    else:
        raise ValueError('%r cannot be read as an astring.' % value)


def nstring(value):
    """Interpret a parsed value as an nstring.

    An nstring is a string that is always represented as a string literal. It
    may be non-existent which is denoted by the special form NIL (parsed as an
    atom with the value 'NIL').

    >>> nstring('foo')
    'foo'

    >>> nstring(Atom('bar'))
    Traceback (most recent call last):
    ValueError: <IMAP atom bar> cannot be read as an nstring.

    >>> repr(nstring(Atom('NIL')))
    'None'

    >>> nstring(['foo', 'bar'])
    Traceback (most recent call last):
    ValueError: ['foo', 'bar'] cannot be read as an nstring.

    """
    if isinstance(value, str):
        return value
    elif isinstance(value, Atom) and value.value == 'NIL':
        return None
    else:
        raise ValueError('%r cannot be read as an nstring.' % value)


def mailbox(value):
    """Interpret a parsed value as a mailbox name.

    Mailbox names are astrings with the value 'INBOX' being treated specially.

    >>> mailbox('foo/bar')
    'foo/bar'

    >>> mailbox('INBOX')
    'INBOX'

    >>> mailbox('iNbOx')
    'INBOX'

    # XXX Clarify what should happen for 'iNbOx/foo'.

    """
    value = astring(value)
    if value.upper() == 'INBOX':
        return 'INBOX'
    else:
        return value


def number(value):
    """Interpret a parsed value as a number.

    Numbers are represented by atoms whose value is a decimal representation
    of the number.

    >>> number(Atom('42'))
    42

    >>> number(Atom('foo'))
    Traceback (most recent call last):
    ValueError: <IMAP atom foo> cannot be read as a number.

    >>> number(42)
    Traceback (most recent call last):
    ValueError: 42 cannot be read as a number.

    """
    try:
        return int(value.value)
    except (AttributeError, ValueError):
        raise ValueError('%r cannot be read as a number.' % value)


NIL = Atom('NIL')
