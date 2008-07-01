# Copyright (c) 2008 gocept gmbh & co. kg
# See also LICENSE.txt
# $Id$

import zope.interface


class IAccount(zope.interface.Interface):
    """An IMAP account.

    Provides live access to the account on the server.

    """

    def get_messages():
        """List messages in INBOX.
        """
