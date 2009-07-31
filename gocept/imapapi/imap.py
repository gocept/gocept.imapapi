# vim:fileencoding=utf-8
# Copyright (c) 2008-2009 gocept gmbh & co. kg
# See also LICENSE.txt
"""Wrapper for IMAP connections to allow some experiments."""

import imaplib
import logging
import socket

logger = logging.getLogger('gocept.imapapi.imap')
socket.setdefaulttimeout(3) # set a default timeout for IMAP connections


def callable_proxy(name, callable):
    def proxy(*args, **kw):
        log_args = args
        if name.startswith('login'):
            user, password = args
            log_args = (user, '****')
        logger.debug('%s(%s, %s)' % (name, log_args, kw))
        return callable(*args, **kw)
    return proxy


class IMAPConnection(object):
    """A facade to the imaplib server connection which provides caching and
    exception handling.

    """

    _selected_path = None

    def __init__(self, host, port, ssl=False):
        if ssl:
            self.server = imaplib.IMAP4_SSL(host, port)
        else:
            self.server = imaplib.IMAP4(host, port)
        logger.debug('connect(%s, %s)' % (host, port))

    def __getattr__(self, name):
        attr = getattr(self.server, name)
        if callable(attr):
            attr = callable_proxy(name, attr)
        return attr

    @property
    def selected_path(self):
        if self.server.state != 'SELECTED':
            return None
        return self._selected_path

    def select(self, path):
        select = callable_proxy('select', self.server.select)
        code, data = select(path)
        if code == 'OK':
            self._selected_path = path
        return code, data
