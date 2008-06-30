# Copyright (c) 2008 gocept gmbh & co. kg
# See also LICENSE.txt
# $Id$

import zope.interface
import zope.schema


class IAccount(zope.interface.Interface):
    """An IMAP account.
    """

    host = zope.schema.TextLine(title=u'Host name')
    port = zope.schema.Int(title=u'Server port')
    user = zope.schema.TextLine(title=u'User name')
    password = zope.schema.TextLine(title=u'Password')

    def get_messages():
        """List messages in INBOX.
        """
