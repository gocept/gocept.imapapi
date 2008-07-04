# Copyright (c) 2008 gocept gmbh & co. kg
# See also LICENSE.txt
# $Id$

import zope.interface
import zope.interface.common.mapping


class IAccountContent(zope.interface.Interface):
    """Something that resides in the object hierarchy of an account.

    """

    name = zope.interface.Attribute('The name.')

    parent = zope.interface.Attribute('The parent node in the hierarchy.')


class IMessage(IAccountContent):
    """A message.

    Provides a mapping of RfC822-style headers.

    """

    headers = zope.interface.Attribute(
        'A dictionary-like object providing access to the headers.')

    raw = zope.interface.Attribute(
        'The raw text content of the whole message. '
        'Includes headers and body. No encoding conversions are applied. ')

    text = zope.interface.Attribute(
        'The body of the message as text/plain.')


class IFolderContainer(zope.interface.Interface):
    """An object which contains IMAP folders.

    IMAP folders are IFolder objects.

    """

    def folders():
        """The folders in this account.

        Sorted alphabetically.

        """


class IMessageContainer(zope.interface.Interface):
    """An object which contains IMAP messages.

    Messages are IMessage objects.

    """

    def messages(name=None):
        """Retrieve a list of messages.

        If name is given, then only the message with the name is returned.

        Otherwise all messages are retrieved.

        """


class IAccount(IFolderContainer):
    """An IMAP account.

    Provides live access to the account on the server.

    """


class IFolder(IFolderContainer, IMessageContainer, IAccountContent):
    """An IMAP folder.

    Contains messages and other folders.

    """


