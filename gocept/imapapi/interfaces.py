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


class IMessage(zope.interface.common.mapping.IMapping,
               IAccountContent):
    """A message.

    Provides a mapping of RfC822-style headers.

    """


class IFolderContainer(zope.interface.Interface):
    """An object which contains IMAP folders.

    IMAP folders are IFolder objects.

    """

    folders = zope.interface.Attribute('The folders in this account.')


class IMessageContainer(zope.interface.Interface):
    """An object which contains IMAP messages.

    Messages are IMessage objects.

    """

    messages = zope.interface.Attribute('The messages in this folder.')


class IAccount(IFolderContainer):
    """An IMAP account.

    Provides live access to the account on the server.

    """


class IFolder(IFolderContainer, IMessageContainer, IAccountContent):
    """An IMAP folder.

    Contains messages and other folders.

    """


