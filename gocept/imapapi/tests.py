# vim:fileencoding=utf-8
# Copyright (c) 2008 gocept gmbh & co. kg
# See also LICENSE.txt
# $Id$
"""Test harness for gocept.imapapi."""

import unittest
from zope.testing import doctest

import imaplib
import gocept.imapapi.parser


def callIMAP(server, function, *args, **kw):
    status, data = getattr(server, function)(*args, **kw)
    assert status == 'OK'
    return data


def setUp(self):
    server = imaplib.IMAP4('localhost', 10143)
    server.login('test', 'bsdf')
    # Clean up the test account from previous runs. We do not delete at the
    # end of a run to preserve data for debugging purposes.
    data = callIMAP(server, 'list')
    names = []
    for response in data:
        flags, sep, name = gocept.imapapi.parser.mailbox_list(response)
        names.append(name)
    for name in reversed(sorted(names)):
        if name == 'INBOX':
            # The INBOX can't be deleted.
            continue
        callIMAP(server, 'delete', name)

    # Clear the INBOX from messages as we couldn't delete it earlier.
    data = callIMAP(server, 'select', 'INBOX')
    if int(data[0]) >= 1:
        data = callIMAP(server, 'store', '1:*', '+FLAGS', '\\Deleted')
    callIMAP(server, 'expunge')

    # Create a message in the INBOX
    message = 'From: test@localhost\nSubject: Foo\n\nEverything is ok!'
    callIMAP(server, 'append', 'INBOX', '', '"02-Jul-2008 03:05:00 +0200"',
             message)

    # Create the standard hierarchy for tests
    callIMAP(server, 'create', 'INBOX/Baz')
    callIMAP(server, 'create', 'Bar')
    status, data = server.logout()
    assert status == 'BYE'


optionflags = doctest.NORMALIZE_WHITESPACE | doctest.ELLIPSIS

def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(doctest.DocFileSuite(
        'account.txt',
        'folder.txt',
        setUp=setUp,
        optionflags=optionflags))
    suite.addTest(doctest.DocTestSuite(
        'gocept.imapapi.parser',
        optionflags=optionflags))
    return suite
