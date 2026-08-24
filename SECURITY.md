# Security

## Reporting a vulnerability

Email **support@seekquel.app** with the details. Please do not open a public issue for
anything exploitable.

Include what you found, how to reproduce it, and what an attacker could do with it. You
will get an acknowledgement within a few days.

## What is worth reporting

- Anything that lets one account read or write another account's reading data.
- Anything that leaks a device key, or lets a device key be guessed or reused.
- Anything that lets the pairing exchange be completed by somebody who is not the reader
  approving it.
- Anything that lets a sync write to a book, column or library it was not pointed at.

## Known and deliberate

**The device key is stored in plain text** in Calibre's own configuration directory, in
`plugins/Seekquel Sync.json`. Calibre offers plugins no keystore, and a file on a
reader's own machine is readable by anything already running as that reader, so an
encrypted copy would only look like protection. Two things bound what the key is worth:
it is scoped to syncing and can neither read nor change account settings, and it is
revocable at any time from Settings, Integrations in Seekquel.

**The key is never typed or pasted.** The plugin obtains it through the pairing exchange
below, so it does not exist anywhere a reader might copy it to. This is deliberate: the
usual alternative is asking somebody to paste a long-lived account API token into a
desktop app, which is a much larger secret sitting in the same unprotected file.

**The pairing code is eight characters** and lives for fifteen minutes behind a human
approval on an account somebody is already signed in to. The device code that backs the
exchange is 64 characters and is stored hashed.

**HTTPS is verified.** Certificate checking is only skipped for a plain `http://`
address, which exists so the plugin can be run against a local development server.
