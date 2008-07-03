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


uidvalidity_re = re.compile(r'^".*?" \(UIDVALIDITY (?P<uidvalidity>[0-9]+)\)$')


def uidvalidity(line):
    """Parse an IMAP `status` response to a UIDVALIDITY query.
    """
    match = uidvalidity_re.match(line)
    return int(match.groupdict()['uidvalidity'])


message_uid_other_re = re.compile(r'^[0-9]+ \(UID (?P<uid>[0-9]+)')


def message_uid_other(line):
    """Parse an IMAP `fetch` response asking for a UID.
    """
    match = message_uid_other_re.match(line)
    return int(match.groupdict()['uid'])
