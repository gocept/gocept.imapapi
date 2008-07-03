# Copyright (c) 2008 gocept gmbh & co. kg
# See also LICENSE.txt
# $Id$


import zope.interface

import gocept.imapapi.interfaces


class Message(dict):

    zope.interface.implements(gocept.imapapi.interfaces.IMessage)

    __allow_access_to_unprotected_subobjects__ = True

    def __init__(self, name, parent, headers):
        super(Message, self).__init__(headers)
        self.name = name
        self.parent = parent
