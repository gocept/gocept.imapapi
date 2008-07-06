# vim:fileencoding=utf-8
# Copyright (c) 2008 gocept gmbh & co. kg
# See also LICENSE.txt
# $Id$
"""Parsing IMAP responses."""

import re


mailbox_list_re = re.compile(
    r'^\((?P<flags>.*?)\) "(?P<sep>.)" "(?P<name>.*)"$')


def mailbox_list(line):
    r"""Parse an IMAP `mailbox_list` response.

    Returns a tuple: (flags, separator, name)

    Currently this is only intended to handle responses as dovecot returns
    them:

    >>> mailbox_list('(\\Noselect \\HasChildren) "/" "INBOX/Baz"')
    ('\\Noselect \\HasChildren', '/', 'INBOX/Baz')
    >>> mailbox_list('(\\NoInferiors \\UnMarked) "/" "INBOX/Baz/qux"')
    ('\\NoInferiors \\UnMarked', '/', 'INBOX/Baz/qux')

    """
    match = mailbox_list_re.match(line)
    groups = match.groupdict()
    return (groups['flags'], groups['sep'], groups['name'])


uidvalidity_re = re.compile(r'.*?\(UIDVALIDITY (?P<uidvalidity>[0-9]+)\)$')


def uidvalidity(line):
    """Parse an IMAP `status` response to a UIDVALIDITY query.
    """
    match = uidvalidity_re.match(line)
    return int(match.groupdict()['uidvalidity'])


# message_uid_other_re = re.compile(r'^[0-9]+ \(UID (?P<uid>[0-9]+)')


# def message_uid_other(line):
#     """Parse an IMAP `fetch` response asking for a UID.
#     """
#     match = message_uid_other_re.match(line)
#     return int(match.groupdict()['uid'])


def message_uid_headers(data):
    """Parse an IMAP `fetch` response for UID and RFC822.HEADER.
    """
    data = ''.join('\r\n'.join(parts) for parts in data)
    tokens = tokenize(data)
    uid = tokens[1][1]
    headers = tokens[1][3]
    return uid, headers

def _parse_structure(structure, path): 
    if isinstance(structure[0], str):
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
    data['partnumber'] = path
    return data

def _parse_nonmultipart(element, path):
    data = {}
    data['content_type'] = '%s/%s' % (element[0].lower(), element[1].lower())
    data['parameters'] = {}
    if isinstance(element[2], list):
        while element[2]:
            data['parameters'][element[2].pop().lower()] = element[2].pop()
    data['id'] = element[3]
    data['description'] = element[4]
    data['encoding'] = element[5].lower()
    data['size'] = element[6]
    data['partnumber'] = path
    return data

def message_structure(data):
    """Parse an IMAP `fetch` response for BODYSTRUCTURE.
    """
    tokens = tokenize(data)
    assert len(tokens) == 2
    structure = tokens[1][3]
    structure = _parse_structure(structure, '')
    return structure


ATOM_CHARS = [chr(i) for i in xrange(32, 256) if chr(i) not in r'(){ %*"\]']


class TokenizeError(Exception):
    def __init__(self, msg, data):
        Exception.__init__(self, "%s in '%s' at index %s." %
                           (msg, data.string, data.index))


class LookAheadStringIter(object):
    """String iterator that allows looking one character ahead.

    >>> i = LookAheadStringIter('abcd')
    >>> i.ahead
    'a'
    >>> i.next()
    'a'
    >>> i.ahead
    'b'
    >>> i.next()
    'b'
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
    """

    index = -1

    def __init__(self, string):
        self.string = string
        self.iter = iter(string)
        if string:
            self.ahead = self.iter.next()
        else:
            self.ahead = None

    def next(self):
        self.index += 1
        result = self.ahead
        if result:
            try:
                self.ahead = self.iter.next()
            except StopIteration:
                self.ahead = None
            return result
        else:
            raise StopIteration

    def __iter__(self):
        return self

_ = LookAheadStringIter


class Atom(object):
    """An IMAP atom.

    >>> repr(Atom('foo'))
    '<IMAP atom foo>'

    >>> str(Atom('foo'))
    'foo'

    >>> repr(Atom('nil'))
    'None'
    >>> Atom('nil') is None
    True

    """

    def __new__(cls, value):
        if value.lower() == 'nil':
            return None
        try:
            number = int(value)
        except ValueError:
            pass
        else:
            return number
        return object.__new__(cls)

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
        raise TokenizeError('Unexpected end of quoted string', data)
    return result


def read_literal(data):
    r"""Read a literal string from an IMAP response.

    >>> read_literal(_('{4}\r\nasdf'))
    'asdf'

    >>> read_literal(_('{4}\r\na\\s\x1adf'))
    'a\\s\x1a'

    """
    assert data.next() == '{'
    count = ''
    for c in data:
        if c == '}':
            break
        count += c
    if not (data.ahead and data.next() == '\r' and
            data.ahead and data.next() == '\n'):
        raise TokenizeError('Syntax error in literal string', data)
    try:
        count = int(count)
    except ValueError:
        raise TokenizeError(
            'Non-integer token for length of literal string', data)

    result = ''
    for c in data:
        result += c
        count -= 1
        if not count:
            break
    else:
        raise TokenizeError('Unexpected end of literal string', data)
    return result


def read_list(data):
    """Read a parenthesized list from an IMAP response.

    >>> read_list(_('(foo "bar")'))
    [<IMAP atom foo>, 'bar']

    >>> read_list(_('(foo "bar" (baz)) qux'))
    [<IMAP atom foo>, 'bar', [<IMAP atom baz>]]

    """
    assert data.next() == '('
    result = list(tokenize_recursive(data))
    if not data.ahead or data.next() != ')':
        raise TokenizeError('Unexpected end of list', data)
    return result


def read_atom(data):
    """Read an atom from an IMAP response.

    >>> read_atom(_('foo'))
    <IMAP atom foo>

    >>> read_atom(_('bar baz'))
    <IMAP atom bar>

    >>> print read_atom(_('nil'))
    None

    >>> print read_atom(_('1234'))
    1234

    """
    assert data.ahead in ATOM_CHARS
    result = ''
    while data.ahead in ATOM_CHARS:
        result += data.next()
    return Atom(result)


def read_flag(data):
    """Read a flag from an IMAP response.

    >>> read_flag(_('\\\\Flag'))
    <IMAP flag \\Flag>

    """
    assert data.next() == '\\'
    return Flag(read_atom(data).value)


def tokenize_recursive(data):
    """Tokenize an IMAP response until the end of the current nested list.

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
            raise TokenizeError('Syntax error %s' % c, data)


def tokenize(data):
    r"""Tokenize an IMAP response with no regard to numerals and NIL.

    >>> tokenize('')
    []

    >>> tokenize('foo "bar"')
    [<IMAP atom foo>, 'bar']

    >>> tokenize('(\\Noselect \\Marked) "/" INBOX/Foo/bar')
    [[<IMAP flag \Noselect>, <IMAP flag \Marked>], '/',
     <IMAP atom INBOX/Foo/bar>]

    >>> tokenize('''(UID 17 RFC822 {58}\r\n\
    ... From: foo@example.com
    ... Subject: Test
    ...
    ... This is a test mail.
    ...  FLAGS (\\Deleted))''')
    [[<IMAP atom UID>, 17, <IMAP atom RFC822>,
     'From: foo@example.com\nSubject: Test\n\nThis is a test mail.\n',
     <IMAP atom FLAGS>, [<IMAP flag \Deleted>]]]

    >>> tokenize(r'(BODYSTRUCTURE ("TEXT" "PLAIN")("TEXT" "HTML"))')
    [[<IMAP atom BODYSTRUCTURE>, ['TEXT', 'PLAIN'], ['TEXT', 'HTML']]]
    >>> tokenize(r'(BODYSTRUCTURE ("TEXT" "PLAIN") ("TEXT" "HTML"))')
    [[<IMAP atom BODYSTRUCTURE>, ['TEXT', 'PLAIN'], ['TEXT', 'HTML']]]

    """
    data = LookAheadStringIter(data)
    result = list(tokenize_recursive(data))
    if data.ahead:
        raise TokenizeError('Inconsistent nesting of lists', data)
    return result
