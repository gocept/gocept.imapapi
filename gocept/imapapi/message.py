# Copyright (c) 2008 gocept gmbh & co. kg
# See also LICENSE.txt
# $Id$


import zope.interface

import Acquisition

import gocept.imapapi.interfaces


class Message(Acquisition.Explicit, dict):

    zope.interface.implements(gocept.imapapi.interfaces.IMessage)

    __allow_access_to_unprotected_subobjects__ = True
