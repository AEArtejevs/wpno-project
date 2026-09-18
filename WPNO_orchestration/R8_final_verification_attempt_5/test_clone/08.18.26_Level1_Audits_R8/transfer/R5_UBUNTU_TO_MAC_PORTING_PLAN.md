# R5 — UBUNTU TO MAC PORTING PLAN

**Status: PREPARED, NOT IN EFFECT.** This plan describes what happens after
R5 is frozen. R5 is not frozen. The transfer inventory and transfer manifest
that accompany it are created at freeze time, because they have to bind the
frozen bytes and nothing else.

Nothing in this invocation touched, synchronised with, or modified the Mac.

## The rule

**Do not run a frozen Ubuntu R5 unchanged on macOS if Ubuntu absolute paths or
executables are bound into it.**

R5 is Ubuntu-native by instruction, and it is Ubuntu-native in fact. That is
not a cosmetic property, and the differences are not hypothetical — every one
below was measured on this machine during the build.

## What is bound to Ubuntu

**The openssl applet is a different program.** macOS ships LibreSSL; this
machine has OpenSSL 3.5.5. They disagree about arguments R5 depends on:

* LibreSSL's `verify` does not implement the `--` end-of-options separator.
  That single difference is what produced L1-A31 RUN-A ERROR in R4: five
  operations exited 1 with a usage block before reading a certificate.
* `-no-CAfile`, `-no-CApath` and `-no-CAstore` are how R5 refuses default and
  system trust. They are OpenSSL 3 options. If they are absent, the refusal
  silently does not happen and a chain could verify against a CA the audit
  never named — with an identical exit code.
* The two report a DER file passed to `-CAfile` differently: LibreSSL as
  `Error loading file`, OpenSSL 3.5.5 as a certificate verify error. Neither
  says "this file is DER".

**Executable paths.** `automation/policy.py` binds absolute paths. All nine
exist on this machine. `/usr/bin/shasum` and `/usr/bin/python3` exist on both
platforms but are not the same builds, and `/usr/bin/openssl` is a different
program entirely, as above.

**Locale.** `ENV_FIXED` sets `LC_ALL=C.UTF-8`. On this machine that is a real
installed locale and umlauts round-trip. CLAUDE.md § 8 records that on the
macOS build it is not a real locale and falls back to ASCII, destroying every
umlaut. The value is unchanged, but its behaviour is not.

**Python.** This machine has 3.14.4 with a working `pyexpat`. CLAUDE.md § 8
records that the Homebrew 3.14 on the Mac has a broken `pyexpat` and that XML
and DOCX work must use `/usr/bin/python3` there. R5 was neither built nor
tested against that interpreter.

**Filesystem semantics.** This filesystem is case-sensitive; the Mac's is
case-insensitive by default. `path_policy` already handles the collision
explicitly, and the RUN-B isolation check normalises case — but the *tests*
that prove it were run here, where the two spellings are genuinely two names.
On a case-insensitive filesystem they are one, and the test proves something
weaker.

**Unicode normalisation.** macOS normalises to NFD on disk while an argument
may arrive as NFC. The isolation check generates both forms. That path is
exercised here only synthetically, because this filesystem does not do the
conversion for us.

## The procedure

1. **Freeze R5 on Ubuntu.** Only after independent verification passes and the
   human freeze token is supplied.

2. **Transfer frozen R5 to the Mac as evidence first.** It arrives as a record
   of what was built and verified on Ubuntu. It is not executed there. Verify
   `transfer/R5_UBUNTU_TRANSFER_MANIFEST.sha256` on arrival; a transfer that
   is not hash-verified on the far side has not been shown to have arrived.

3. **Create a separate Mac-native sibling revision or profile.** Do not edit
   frozen R5 in place. The Mac revision declares its own `paths.json`, its own
   executable table, and its own locale, and it re-derives them by measurement
   on that machine.

4. **Independently verify the Mac revision's paths and tools before executing
   anything.** At minimum: every executable in the table exists and reports a
   version; the openssl applet accepts the exact argv the catalogue emits, and
   in particular the default-trust refusal flags; the five required controls
   behave as required *there*; `LC_ALL` round-trips an umlaut; the interpreter
   used for XML and DOCX has a working `pyexpat`.

5. **Run the complete test cycle and the pass-readiness fixtures on the Mac**
   before any audit phase. A suite that passed on Ubuntu says nothing about
   the Mac.

## What must not happen

- Frozen Ubuntu R5 is not executed on macOS.
- Frozen R5 is not edited to make it run there.
- The Mac is not synchronised with, or modified from, the Ubuntu machine as a
  side effect of the transfer.
- No R5 approval token is reused on the Mac revision. Tokens bind a plan, and
  a Mac plan is a different plan.
