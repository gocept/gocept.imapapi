==============
gocept.imapapi
==============

This package provides an object-oriented API for accessing IMAP servers. It
was written to provide an API that is simple to use while still maintaining
good performance.

.. contents::

About
=====

`gocept.imapapi` is sponsored by the `Technical University of Munich`_ as part
of a research co-operation geared towards an integrated webmail system for the
university's student portal `MyTum`_. Other components of this project include
`gocept.restmail` and `CMFWebmail`.

This project was initially developed by `gocept gmbh & co. kg`_.

Object-oriented API
===================

One of the first goals of the webmail project was to factor out the
lower-level utilities to allow others to build on our efforts.

This library takes on to provide a better abstracted, more object-oriented,
well, more `pythonic` approach than the builtin `imaplib` does.

Let us give you an example of what we feel a good API looks like:

  >>> from gocept.imapapi import Account
  >>> account = Account('localhost', 10143, 'tim', 'mightywizard')
  >>> account.folders.keys()
  ['INBOX']
  >>> account.folders['INBOX'].messages
  <Messages object at 0x...>
  >>> for message in account.folders['INBOX'].messages.values():
  ...     repr(message.headers['subject'])
  u'Re: your spell from last week'
  u'Enlarge your magic wand!'

Some of the aspects that come to mind when looking at this example:

- Object model on top of protocol specifics
- Use of native Python data structures
- Decode protocol-specific data as early as possible (see the unicode headers)

With this approach we try to make programming IMAP clients simpler and more
convenient.

Performance
===========

The imapapi layer tries to keep the amount and size of communication as small
as possible, only retrieving data when really needed and re-using data already
retrieved.

As an examples, body content isn't downloaded until needed and even when
looking at the body structure we differentiate between metadata and content.

Status
======

This package is still in early development and published for experimental
purposes and to invite a wider community to join us developing an IMAP library
that is more convenient than Python's builtin `imaplib`.

Running the tests
=================

The tests expect an IMAP server to be available on localhost:10143. The
default buildout environment provides a `dovecot`_ installation for this.

As we aim to be compatible with as many IMAP servers as possible, you should
be able to provide any IMAP server on this port, as long as a user 'test' with
the password 'bsdf' is configured.

Warning: Do not let the tests run against a production system. They *might*
wreak havoc.


.. _`Technical University of Munich`: http://www.tum.de

.. _`MyTum`: http://portal.mytum.de

.. _`gocept gmbh & co. kg`: http://www.gocept.com

.. _`dovecot`: http://www.dovecot.org
