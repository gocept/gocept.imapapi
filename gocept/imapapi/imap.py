# vim:fileencoding=utf-8
# Copyright (c) 2008-2009 gocept gmbh & co. kg
# See also LICENSE.txt
"""Wrapper for IMAP connections to allow some experiments."""

import imaplib
import logging

logger = logging.getLogger('gocept.imapapi.imap')


def callable_proxy(conn, name, callable):
    def proxy(*args, **kw):
        log_args = args
        if name.startswith('login'):
            user, password = args
            log_args = (user, '****')
        logger.debug('%s:%s: %s(%s, %s)' % (
                conn.server.host, conn.server.port, name, log_args, kw))
        try:
            return callable(*args, **kw)
        except:
            logger.debug('Error in %s' % name, exc_info=True)
            raise
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
            attr = callable_proxy(self, name, attr)
        return attr

    @property
    def selected_path(self):
        if self.server.state != 'SELECTED':
            return None
        return self._selected_path

    def select(self, path):
        select = callable_proxy(self, 'select', self.server.select)
        code, data = select(path)
        if code == 'OK':
            self._selected_path = path
        return code, data
