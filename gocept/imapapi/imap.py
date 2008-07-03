# vim:fileencoding=utf-8
# Copyright (c) 2008 gocept gmbh & co. kg
# See also LICENSE.txt
# $Id$
"""Wrapper for IMAP connections to allow some experiments."""

import imaplib


def callable_proxy(name, callable):
    def proxy(*args, **kw):
        print "IMAP call", name, args, kw
        return callable(*args, **kw)
    return proxy


class IMAPConnection(object):
    """A facade to the imaplib server connection which provides caching and
    exception handling.

    """

    def __init__(self, host, port):
        self.server = imaplib.IMAP4(host, port)

    def __getattr__(self, name):
        attr = getattr(self.server, name)
        if callable(attr):
            attr = callable_proxy(name, attr)
        return attr
