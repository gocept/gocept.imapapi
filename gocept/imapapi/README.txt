==============
gocept.imapapi
==============

This package provides an object-oriented API for accessing IMAP servers. It
was written to provide an API is simple to use while still maintaining good
performance.

.. contents:



Running the tests
=================

The tests expect an IMAP server to be available on localhost:10143. The
default buildout environment provides a dovecot installation for this.

As we aim to be compatible to as many IMAP servers as possible, you should be
able to provide any IMAP server on this port, as long as a user 'test' with the
password 'bsdf' is configured.

Warning: Do not let the tests run against a production system. They *might*
wreak havoc.
