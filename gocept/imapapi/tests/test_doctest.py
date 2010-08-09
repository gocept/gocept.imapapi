# Copyright (c) 2008 gocept gmbh & co. kg
# See also LICENSE.txt

import doctest
import gocept.imapapi.testing
import re
import unittest
import zope.testing.renormalizing

checker = zope.testing.renormalizing.RENormalizing([
    (re.compile('0x[0-9a-f]+'), "<MEM ADDRESS>")])


optionflags = (doctest.NORMALIZE_WHITESPACE | doctest.ELLIPSIS |
               doctest.REPORT_NDIFF)


def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(doctest.DocFileSuite(
        'imap.txt',
        'account.txt',
        'folder.txt',
        'message.txt',
        'optimizations.txt',
        package='gocept.imapapi',
        setUp=gocept.imapapi.testing.setUp,
        optionflags=optionflags,
        checker=checker))
    suite.addTest(doctest.DocTestSuite(
        'gocept.imapapi.parser',
        optionflags=optionflags))
    suite.addTest(doctest.DocTestSuite(
        'gocept.imapapi.folder',
        optionflags=optionflags))
    return suite
