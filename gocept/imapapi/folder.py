# Copyright (c) 2008-2009 gocept gmbh & co. kg
# See also LICENSE.txt
# $Id: account.py 12226 2008-07-01 13:39:31Z thomas $

import UserDict
import email.Parser
import gocept.imapapi.interfaces
import gocept.imapapi.message
import gocept.imapapi.parser
import zope.interface


class Folder(object):

    zope.interface.implements(gocept.imapapi.interfaces.IFolder)

    def __init__(self, name=None, parent=None, separator=None,
                 encoded_name=None):
        self.name = name
        self.encoded_name = encoded_name
        if encoded_name is None and name is not None:
            self.encoded_name = encode_modified_utf7(name)
        if name is None and encoded_name is not None:
            self.name = decode_modified_utf7(encoded_name)
        self.parent = parent
        self._separator = separator

    def __repr__(self):
        repr = super(Folder, self).__repr__()
        return repr.replace('object', 'object %r' % self.path)

    def __eq__(self, other):
        if not isinstance(other, Folder):
            return False
        if self.server is not other.server:
            return False
        return self.path == other.path

    @property
    def server(self):
        return self.parent.server

    @property
    def is_subfolder(self):
        return gocept.imapapi.interfaces.IFolder.providedBy(self.parent)

    @property
    def depth(self):
        if self.is_subfolder:
            return self.parent.depth + 1
        else:
            return 1

    @property
    def separator(self):
        # RfC 3501 requires to always use the same separator as given by the
        # top-level node.
        if self.is_subfolder:
            return self.parent.separator
        else:
            return self._separator

    @property
    def path(self):
        if self.is_subfolder:
            return self.parent.path + self.separator + self.name
        else:
            return self.name

    @property
    def encoded_path(self):
        if self.is_subfolder:
            return (self.parent.encoded_path + self.separator
                    + self.encoded_name)
        else:
            return self.encoded_name

    @property
    def folders(self):
        return Folders(self)

    @property
    def messages(self):
        return gocept.imapapi.message.Messages(self)

    _message_count_cache = None

    @property
    def message_count(self):
        """Returns the number of messages in the folder.

        The number is cached during the transaction. Since RfC 3501 states
        that the STATUS command should not be used on the currently selected
        mail box, the same value will be set when selecting the folder.

        """
        if self._message_count_cache is None:
            code, data = self.server.status(self.encoded_path, "(MESSAGES)")
            assert code == 'OK'
            self._message_count_cache = (
                gocept.imapapi.parser.status(data[0])['MESSAGES'])
        return self._message_count_cache

    def _select(self):
        """Selects the folder as the current folder of the connection.

        Caches the number of messages in the folder. If the folder is already
        selected, this is a no-op.

        """
        if self.server.selected_path != self.encoded_path:
            code, data = self.server.select(self.encoded_path)
            assert code == 'OK', 'Unexpected status code %s' % code
            self._message_count_cache = int(data[0])

    _uidvalidity = None

    @property
    def uidvalidity(self):
        """Retrieve the UID validity value of the folder.

        This number must stay the same throughout a session.

        """
        if self._uidvalidity is None:
            code, data = self.server.status(
                self.encoded_path, "(UIDVALIDITY)")
            self._uidvalidity = (
                gocept.imapapi.parser.status(data[0])['UIDVALIDITY'])
        return self._uidvalidity


class Folders(UserDict.DictMixin):
    """A mapping object for accessing folders located in IFolderContainers.
    """

    zope.interface.implements(gocept.imapapi.interfaces.IFolders)

    def __init__(self, container):
        self.container = container

    _keys = None

    def keys(self):
        if self._keys is not None:
            return self._keys

        if gocept.imapapi.interfaces.IFolder.providedBy(self.container):
            if self.container.separator is not None:
                path = self.container.encoded_path + self.container.separator
            else:
                # We have a non-hierarchical folder.
                return []
        else:
            path = ''

        code, data = self.container.server.list('', path + '%')
        assert code == 'OK'

        result = []
        for response in gocept.imapapi.parser.unsplit(data):
            if response is None:
                continue
            flags, sep, name = gocept.imapapi.parser.mailbox_list(response)
            # XXX Looping the separator this way is kind of icky.
            self.separator = sep
            if sep is not None:
                name = name.split(sep)[-1]
            name = decode_modified_utf7(name)
            result.append(name)
        result.sort()

        self._keys = result
        return result

    def __getitem__(self, key):
        key = unicode(key)
        if key not in self.keys():
            raise KeyError(key)
        # XXX Part two of the icky separator communication
        return Folder(key, self.container, self.separator)

    def __setitem__(self, key, folder):
        assert isinstance(key, unicode)
        if not isinstance(folder, Folder):
            raise ValueError('Can only store folder objects.')
        if (folder.name is not None or
            folder.parent is not None):
            raise ValueError('Can only assign unattached folder objects.')

        encoded_key = encode_modified_utf7(key)
        if gocept.imapapi.interfaces.IFolder.providedBy(self.container):
            path = (self.container.encoded_path + self.container.separator +
                    encoded_key)
        else:
            path = encoded_key

        code, data = self.container.server.create(path)
        if code == 'NO':
            raise gocept.imapapi.interfaces.IMAPError(
                "Could not create folder '%s': %s" % (path, data[0]))
        assert code == 'OK'

        folder.name = key
        folder.encoded_name = encoded_key
        folder.parent = self.container
        if self._keys is not None:
            self._keys.append(key)
            self._keys.sort()


def encode_modified_utf7(text):
    r"""Modified UTF-7 encoding as specified in RfC 3501, section 5.1.3.

    >>> encode_modified_utf7(u'\xe4\xf6\xfc')
    '&AOQA9gD8-'

    """
    def encode_buffer(buffer):
        return buffer.encode('utf7').replace('/', ',').replace('+', '&')

    bytes = ''
    buffer = u''
    for c in text:
        if u'\x20' <= c <= u'\x7e':
            bytes += encode_buffer(buffer)
            buffer = u''
            if c == u'&':
                bytes += '&-'
            else:
                bytes += c.encode('ascii')
        else:
            buffer += c
    bytes += encode_buffer(buffer)
    return bytes


def decode_modified_utf7(bytes):
    r"""Modified UTF-7 decoding as specified in RfC 3501, section 5.1.3.

    We can decode correctly encoded Unicode:

    >>> decode_modified_utf7('&AOQA9gD8-')
    u'\xe4\xf6\xfc'

    We don't break on junk:

    >>> decode_modified_utf7('\xef')
    u'\\xef'

    """
    def decode_utf7(buffer):
        return buffer.replace('&', '+').replace(',', '/').decode('utf7')

    def decode_ascii(buffer):
        try:
            return buffer.decode('ascii')
        except UnicodeDecodeError:
            return unicode(repr(buffer)[1:-1])

    text = u''
    while '&' in bytes:
        start = bytes.index('&')
        text += decode_ascii(bytes[:start])

        stop = bytes.index('-') + 1
        if stop == start + 2:
            text += u'&'
        else:
            text += decode_utf7(bytes[start:stop])
        bytes = bytes[stop:]
    text += decode_ascii(bytes)
    return text
