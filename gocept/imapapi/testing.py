# Copyright (c) 2008-2010 gocept gmbh & co. kg
# See also LICENSE.txt
"""Test harness for gocept.imapapi."""

import gocept.imapapi
import gocept.imapapi.parser
import imaplib
import imaplib
import os
import os.path
import time
import unittest


def callIMAP(server, function, *args, **kw):
    status, data = getattr(server, function)(*args, **kw)
    assert status == 'OK', (function, args, kw, status, data)
    return data


def clear_inbox(server):
    data = callIMAP(server, 'select', 'INBOX')
    if int(data[0]) >= 1:
        data = callIMAP(server, 'store', '1:*', '+FLAGS', '\\Deleted')
    callIMAP(server, 'expunge')


def load_messages(package, path, server, folder_name):
    # Clean up the test folder from previous runs. We do not delete at the
    # end of a run to preserve data for debugging purposes.
    if folder_name == 'INBOX':
        clear_inbox(server)
    else:
        server.delete(folder_name)
        callIMAP(server, 'create', folder_name)

    # Create messages in the test folder.
    path = os.path.join(os.path.dirname(package.__file__), path)
    for filename in sorted(os.listdir(path)):
        if filename.startswith('.') or filename.endswith('~'):
            continue
        filepath = os.path.join(path, filename)
        timestamp = os.path.getmtime(filepath)
        localtime = time.localtime(timestamp)
        date = time.strftime('"%d-%b-%Y %H:%M:%S +0200"', localtime)
        message = open(filepath).read()
        callIMAP(server, 'append', folder_name, '', date, message)


def setup_account(server):
    # Clean up the test account from previous runs. We do not delete at the
    # end of a run to preserve data for debugging purposes.
    data = callIMAP(server, 'list')
    names = []
    for response in gocept.imapapi.parser.unsplit(data):
        flags, sep, name = gocept.imapapi.parser.mailbox_list(response)
        names.append(name)
    for name in reversed(sorted(names)):
        if name == 'INBOX':
            # The INBOX can't be deleted.
            continue
        callIMAP(server, 'delete', name)

    # Clear the INBOX from messages as we couldn't delete it earlier.
    clear_inbox(server)


def setUp(test):
    server = imaplib.IMAP4('localhost', 10143)
    server.login('test', 'bsdf')

    setup_account(server)

    # Create a message in the INBOX
    load_messages(gocept.imapapi, 'testmessages', server, 'INBOX')

    # Create the standard hierarchy for tests
    callIMAP(server, 'create', 'INBOX/Baz')
    callIMAP(server, 'create', 'INBOX/Baz/Boo')
    callIMAP(server, 'create', 'Bar')
    callIMAP(server, 'create', 'F&APY-')
    status, data = server.logout()
    assert status == 'BYE'

    server = imaplib.IMAP4('localhost', 10143)
    server.login('test2', 'csdf')
    setup_account(server)


class TestCase(unittest.TestCase):

    def setUp(self):
        self.server = imaplib.IMAP4('localhost', 10143)
        self.server.login('test', 'bsdf')
        setup_account(self.server)
