# Copyright (c) 2008 gocept gmbh & co. kg
# See also LICENSE.txt
# $Id$

from setuptools import setup, find_packages


setup(
    name='gocept.imapapi',
    version='0.1',
    author='gocept gmbh & co. kg',
    author_email='mail@gocept.com',
    description='Object-oriented API of an IMAP account.',
    long_description=open(os.path.join(os.path.dirname(__file__), 'gocept',
                                       'imapapi', 'README.txt')).read(),
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    license='ZPL 2.1',
    namespace_packages=['gocept'],
    install_requires=['setuptools'],
)
