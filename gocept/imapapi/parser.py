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
