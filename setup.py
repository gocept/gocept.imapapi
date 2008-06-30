# Copyright (c) 2008 gocept gmbh & co. kg
# See also LICENSE.txt
# $Id$

from setuptools import setup, find_packages


setup(
    name='gocept.imapapi',
    version='1.0',
    author='gocept gmbh & co. kg',
    author_email='mail@gocept.com',
    description='OO and fast API of an IMAP account.',
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    license='ZPL 2.1',
    namespace_packages=['gocept'],
    entry_points="""
    [zc.buildout]
    env = gocept.imapapi.recipe:Environment
    """,
)
