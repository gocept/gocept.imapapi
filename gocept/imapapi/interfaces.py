# Copyright (c) 2008 gocept gmbh & co. kg
# See also LICENSE.txt
# $Id$

import zope.interface
import zope.interface.common.mapping


class IMAPError(Exception):
    """An error raised due to a failed IMAP command."""


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

    def folders(name=None):
        """Retrieve a list of folders.

        Sorted alphabetically.

        If name is given, the resulting list will only contain at most one
        folder, matching the given name.

        """

    def create_folder(name):
        """Create a new folder with the given name.

        If the name is invalid as a folder name, another folder with the same
        name exists in the container already, or some error occured while
        trying to create the folder on the server, an exception is raised.

        Returns the new folder.

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


class IBodyPart(zope.interface.Interface):
    """A part of a message body.

    A dictionary-like object with the message body part's parameters as keys.

    If the body part is of the major content type `multipart` then the `parts`
    attribute contains the sub-parts.

    """

    parts = zope.interface.Attribute("A list of sub-parts.")

    def __getitem__(self, key):
        """Access the property `key` from the body part."""

    def fetch(self):
        """Return a file object containing the data of the body."""
