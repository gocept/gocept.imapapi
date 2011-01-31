# Copyright (c) 2008 gocept gmbh & co. kg
# See also LICENSE.txt

import os
from setuptools import setup, find_packages


setup(
    name='gocept.imapapi',
    version='0.5',
    author='gocept gmbh & co. kg',
    author_email='mail@gocept.com',
    description='Object-oriented API for accessing IMAP accounts.',
    long_description=(
        open(os.path.join(os.path.dirname(__file__),
                          'gocept', 'imapapi', 'README.txt')).read()
        + '\n\n' + open('CHANGES.txt').read()),
    packages=find_packages(),
    include_package_data=True,
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: Zope Public License',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Communications :: Email :: Post-Office :: IMAP',
        'Topic :: Software Development :: Libraries :: Python Modules'],
    zip_safe=False,
    license='ZPL 2.1',
    namespace_packages=['gocept'],
    install_requires=[
        'setuptools',
        'zope.interface',
        'zope.schema',
    ],
)
