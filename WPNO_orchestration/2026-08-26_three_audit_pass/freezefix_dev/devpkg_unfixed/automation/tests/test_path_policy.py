"""Path admission control.

Covers self-test cases 1-7 and 28:
allowed path · outside allowlist · '..' traversal · symlink escape ·
null byte · Unicode path normalization · case-insensitive path collision ·
unexpected write.

The symlink section carries the VF-002 regressions. The predecessor package
canonicalized the path before walking its components, so the component that was
a symlink had already been resolved away and the guard reported success on an
escape. Every one of these tests must be able to fail; none may be relaxed.

The Unicode section carries the R3 correction. R2 failed independent
verification on exactly one test: `TestUnicodeNormalization.test_nfc_and_nfd_agree`
asserted that its two fixture strings differed, and they did not. The composed
character had been written straight into the source literal while a comment
called it decomposed, so the test failed on its own fixture and never reached
the question it existed to ask.

The rebuilt section separates four guarantees that R2 had collapsed into one
assertion, and none of them requires the filesystem to keep NFC and NFD as two
distinct directory entries:

  A. the two spellings are constructed from explicit code points, in memory,
     and are proved to be different sequences before anything is normalized;
  B. both spellings are pushed through the path policy as strings and must
     yield one canonical identity, one read decision and one write decision;
  C. exactly one physical file is created; what macOS does with the second
     spelling is measured and recorded, not required;
  D. normalization is proved not to be a bypass for the allowlist, the symlink
     guard, parent containment, or the one-time approval identity.
"""

import os
import shutil
import unittest

from automation import path_policy, policy
from automation.tests import SELFTEST_DIRNAME


def scratch():
    return path_policy.ensure_dir(
        os.path.join(path_policy.LEVEL1_ROOT, "work", SELFTEST_DIRNAME,
                     "path_policy"))


class TestAllowedPaths(unittest.TestCase):
    """Case 1 — an allowed path is admitted."""

    def test_level1_root_is_readable_and_writable(self):
        self.assertEqual(path_policy.assert_readable(path_policy.LEVEL1_ROOT),
                         path_policy.LEVEL1_ROOT)
        self.assertEqual(path_policy.assert_writable(path_policy.LEVEL1_ROOT),
                         path_policy.LEVEL1_ROOT)

    def test_project_root_is_readable_but_not_writable(self):
        self.assertEqual(path_policy.assert_readable(path_policy.PROJECT_ROOT),
                         path_policy.PROJECT_ROOT)
        with self.assertRaises(path_policy.PathPolicyError):
            path_policy.assert_writable(
                os.path.join(path_policy.PROJECT_ROOT, "anything.txt"))

    def test_discovery_root_is_readable_but_not_writable(self):
        self.assertEqual(path_policy.assert_readable(path_policy.DISCOVERY_ROOT),
                         path_policy.DISCOVERY_ROOT)
        with self.assertRaises(path_policy.PathPolicyError):
            path_policy.assert_writable(
                os.path.join(path_policy.DISCOVERY_ROOT, "anything.txt"))


class TestOutsideAllowlist(unittest.TestCase):
    """Case 2 — a path outside every allowed root is rejected."""

    def test_arbitrary_absolute_path_rejected_for_read(self):
        for candidate in ("/etc/passwd", "/var/log", "/usr/bin/python3"):
            with self.assertRaises(path_policy.PathPolicyError):
                path_policy.assert_readable(candidate)

    def test_protected_home_subdirs_rejected_for_write(self):
        home = os.path.realpath(os.path.expanduser("~"))
        for name in (".codex", ".claude", "Library", ".ssh", ".config"):
            with self.assertRaises(path_policy.PathPolicyError):
                path_policy.assert_writable(os.path.join(home, name, "x"))

    def test_system_prefixes_rejected_for_write(self):
        for candidate in ("/tmp/x", "/private/x", "/Library/x", "/etc/x"):
            with self.assertRaises(path_policy.PathPolicyError):
                path_policy.assert_writable(candidate)

    def test_relative_path_rejected(self):
        with self.assertRaises(path_policy.PathPolicyError):
            path_policy.assert_readable("relative/path")


class TestTraversal(unittest.TestCase):
    """Case 3 — '..' cannot leave an allowed root."""

    def test_dotdot_escape_rejected(self):
        escape = os.path.join(path_policy.LEVEL1_ROOT, "..", "..", "..", "etc")
        with self.assertRaises(path_policy.PathPolicyError):
            path_policy.assert_readable(escape)

    def test_dotdot_that_stays_inside_is_allowed(self):
        inside = os.path.join(path_policy.LEVEL1_ROOT, "prompts", "..", "bindings")
        self.assertEqual(path_policy.assert_readable(inside),
                         os.path.join(path_policy.LEVEL1_ROOT, "bindings"))

    def test_dotdot_write_escape_rejected(self):
        escape = os.path.join(path_policy.LEVEL1_ROOT, "..", "CLAUDE.md")
        with self.assertRaises(path_policy.PathPolicyError):
            path_policy.assert_writable(escape)


class TestSymlinkEscape(unittest.TestCase):
    """Case 4 — a symlink may not lead outside the allowed roots."""

    def setUp(self):
        self.dir = scratch()
        self.link = os.path.join(self.dir, "escape_link")
        if os.path.lexists(self.link):
            os.unlink(self.link)

    def tearDown(self):
        if os.path.lexists(self.link):
            os.unlink(self.link)

    def test_symlink_to_outside_is_rejected(self):
        os.symlink("/etc", self.link)
        with self.assertRaises(path_policy.PathPolicyError):
            path_policy.assert_readable(os.path.join(self.link, "passwd"))

    def test_symlink_component_escape_is_detected(self):
        os.symlink("/etc", self.link)
        with self.assertRaises(path_policy.PathPolicyError):
            path_policy.assert_no_symlink_escape(self.link)

    def test_symlink_inside_roots_is_allowed(self):
        target = path_policy.ensure_dir(os.path.join(self.dir, "target"))
        inner = os.path.join(self.dir, "inner_link")
        if os.path.lexists(inner):
            os.unlink(inner)
        os.symlink(target, inner)
        try:
            self.assertEqual(path_policy.assert_no_symlink_escape(inner),
                             os.path.realpath(target))
        finally:
            os.unlink(inner)


class TestSymlinkComponentRegression(unittest.TestCase):
    """VF-002 — the component must be inspected before it is resolved away."""

    def setUp(self):
        self.dir = path_policy.ensure_dir(os.path.join(scratch(), "vf002"))

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def _link(self, name, target):
        path = os.path.join(self.dir, name)
        if os.path.lexists(path):
            os.unlink(path)
        os.symlink(target, path)
        return path

    def test_ordinary_in_root_path_is_accepted(self):
        real = os.path.join(self.dir, "plain.txt")
        with open(real, "w", encoding="utf-8") as fh:
            fh.write("plain\n")
        self.assertEqual(path_policy.assert_no_symlink_escape(real),
                         os.path.realpath(real))

    def test_direct_outside_path_is_rejected(self):
        with self.assertRaises(path_policy.PathPolicyError):
            path_policy.assert_no_symlink_escape("/etc/passwd")

    def test_final_component_symlink_escape_is_rejected(self):
        link = self._link("final_escape", "/etc/passwd")
        with self.assertRaises(path_policy.PathPolicyError) as ctx:
            path_policy.assert_no_symlink_escape(link)
        self.assertIn("symlink component", str(ctx.exception))

    def test_intermediate_component_symlink_escape_is_rejected(self):
        link = self._link("mid_escape", "/etc")
        candidate = os.path.join(link, "passwd")
        with self.assertRaises(path_policy.PathPolicyError) as ctx:
            path_policy.assert_no_symlink_escape(candidate)
        self.assertIn("symlink component", str(ctx.exception))

    def test_symlink_loop_is_rejected(self):
        a = os.path.join(self.dir, "loop_a")
        b = os.path.join(self.dir, "loop_b")
        for path in (a, b):
            if os.path.lexists(path):
                os.unlink(path)
        os.symlink(b, a)
        os.symlink(a, b)
        with self.assertRaises(path_policy.PathPolicyError) as ctx:
            path_policy.assert_no_symlink_escape(a)
        message = str(ctx.exception).lower()
        self.assertTrue("loop" in message or "depth" in message, message)

    def test_symlink_chain_depth_is_bounded(self):
        end = path_policy.ensure_dir(os.path.join(self.dir, "chain_end"))
        previous = end
        for index in range(policy.MAX_SYMLINK_DEPTH + 2):
            previous = self._link("chain_%02d" % index, previous)
        with self.assertRaises(path_policy.PathPolicyError) as ctx:
            path_policy.assert_no_symlink_escape(previous)
        self.assertIn("depth", str(ctx.exception).lower())

    def test_lexical_absolute_does_not_resolve_a_symlink(self):
        target = path_policy.ensure_dir(os.path.join(self.dir, "lex_target"))
        link = self._link("lex_link", target)
        self.assertEqual(path_policy.lexical_absolute(link), link)
        self.assertNotEqual(path_policy.normalize(link), link)
        self.assertEqual(path_policy.normalize(link), os.path.realpath(target))

    def test_symlink_guard_rejects_a_null_byte(self):
        with self.assertRaises(path_policy.PathPolicyError):
            path_policy.assert_no_symlink_escape(
                os.path.join(self.dir, "a\x00b"))

    def test_symlink_guard_rejects_a_relative_path(self):
        with self.assertRaises(path_policy.PathPolicyError):
            path_policy.assert_no_symlink_escape("work/_selftest")

    def test_in_root_symlink_chain_is_permitted(self):
        end = path_policy.ensure_dir(os.path.join(self.dir, "ok_end"))
        first = self._link("ok_a", end)
        second = self._link("ok_b", first)
        self.assertEqual(path_policy.assert_no_symlink_escape(second),
                         os.path.realpath(end))


class TestNullByte(unittest.TestCase):
    """Case 5 — an embedded null byte is rejected before any syscall."""

    def test_null_byte_rejected(self):
        with self.assertRaises(path_policy.PathPolicyError):
            path_policy.normalize(path_policy.LEVEL1_ROOT + "/x\x00.txt")

    def test_null_byte_rejected_on_write(self):
        with self.assertRaises(path_policy.PathPolicyError):
            path_policy.assert_writable(path_policy.LEVEL1_ROOT + "/a\x00b")


# --------------------------------------------------------------- Unicode
# The two spellings are built here, once, from explicit code points. They are
# never obtained by listing a directory. That is the whole correction: the
# predecessor package wrote the composed character straight into the source
# literal, called it decomposed in a comment, and asserted the two were
# different. They were the same string, so the assertion failed before it ever
# reached the question it existed to ask.
#
# NFC_SOURCE is four code points: U+00FC LATIN SMALL LETTER U WITH DIAERESIS,
# then b, e, r.
# NFD_SOURCE is five: U+0075 LATIN SMALL LETTER U, U+0308 COMBINING DIAERESIS,
# then b, e, r.
#
# Written as escapes on purpose. An escape survives every editor, every
# filesystem, every copy step and every normalizing tool between here and the
# machine that runs the test. A raw character does not, and that is exactly how
# the predecessor's fixture was destroyed.
NFC_SOURCE = "\u00fcber"
NFD_SOURCE = "u\u0308ber"

NFC_CODE_POINTS = (0x00FC, 0x62, 0x65, 0x72)
NFD_CODE_POINTS = (0x0075, 0x0308, 0x62, 0x65, 0x72)

# Set by TestUnicodeFilesystemBehaviour. One physical file, created at most
# once for the whole module.
_UNICODE_FIXTURE = {}

# What the operating system actually did with the two spellings. Recorded, not
# required to be any particular value.
FS_SAME_OBJECT = "SAME_OBJECT"
FS_SEPARATE_ENTRIES = "SEPARATE_ENTRIES"
FS_NFD_NOT_ADDRESSABLE = "NFD_NOT_ADDRESSABLE"
FS_OBSERVATIONS = (FS_SAME_OBJECT, FS_SEPARATE_ENTRIES, FS_NFD_NOT_ADDRESSABLE)


def unicode_scratch():
    return path_policy.ensure_dir(os.path.join(scratch(), "unicode"))


def unicode_fixture():
    """The single physical file the Unicode section is allowed to create.

    At most one file, created once, reused by every test that needs a real
    inode. Nothing here requires the filesystem to keep NFC and NFD as two
    separate directory entries, because that is precisely the assumption that
    is not true on this machine.
    """
    if ("file" not in _UNICODE_FIXTURE
            or not os.path.isfile(_UNICODE_FIXTURE["file"])):
        directory = unicode_scratch()
        created = os.path.join(directory, NFC_SOURCE + ".txt")
        with open(created, "wb") as fh:
            fh.write(b"unicode fixture\n")
        _UNICODE_FIXTURE["dir"] = directory
        _UNICODE_FIXTURE["file"] = created
    return _UNICODE_FIXTURE["dir"], _UNICODE_FIXTURE["file"]


class TestUnicodeNormalization(unittest.TestCase):
    """Case 6 · A — NFC and NFD agree, decided in memory.

    The method name `test_nfc_and_nfd_agree` is the one the predecessor
    package shipped and the one its verification named as failing. It is kept,
    deliberately, so the same method path can be looked up and seen to pass.
    What changed is where its two strings come from.
    """

    def test_nfc_and_nfd_agree(self):
        import unicodedata
        self.assertNotEqual(NFC_SOURCE, NFD_SOURCE)
        self.assertEqual(unicodedata.normalize("NFC", NFC_SOURCE),
                         unicodedata.normalize("NFC", NFD_SOURCE))

    def test_the_two_sources_are_distinct_code_point_sequences(self):
        self.assertEqual(tuple(ord(c) for c in NFC_SOURCE), NFC_CODE_POINTS)
        self.assertEqual(tuple(ord(c) for c in NFD_SOURCE), NFD_CODE_POINTS)
        self.assertEqual(len(NFC_SOURCE), 4)
        self.assertEqual(len(NFD_SOURCE), 5)
        self.assertNotEqual(NFC_CODE_POINTS, NFD_CODE_POINTS)

    def test_each_source_is_already_in_the_form_it_claims(self):
        import unicodedata
        self.assertEqual(unicodedata.normalize("NFC", NFC_SOURCE), NFC_SOURCE)
        self.assertEqual(unicodedata.normalize("NFD", NFD_SOURCE), NFD_SOURCE)
        self.assertNotEqual(unicodedata.normalize("NFD", NFC_SOURCE), NFC_SOURCE)
        self.assertNotEqual(unicodedata.normalize("NFC", NFD_SOURCE), NFD_SOURCE)

    def test_nfd_normalizes_to_nfc_and_back(self):
        import unicodedata
        self.assertEqual(unicodedata.normalize("NFC", NFD_SOURCE), NFC_SOURCE)
        self.assertEqual(unicodedata.normalize("NFD", NFC_SOURCE), NFD_SOURCE)

    def test_the_fixture_does_not_come_from_the_filesystem(self):
        """The regression guard for the failure this package was rebuilt over.

        A raw composed or combining character anywhere in this module's source
        is the defect itself: it means someone wrote the character instead of
        the escape, and an editor or a copy step is free to change it. The
        check reads this file's own bytes and refuses both characters.
        """
        with open(os.path.abspath(__file__), encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn('"\\u00fcber"', text)
        self.assertIn('"u\\u0308ber"', text)
        self.assertNotIn("\u00fc", text)
        self.assertNotIn("\u0308", text)

    def test_normalization_is_idempotent_in_memory(self):
        import unicodedata
        for form in ("NFC", "NFD"):
            for source in (NFC_SOURCE, NFD_SOURCE):
                once = unicodedata.normalize(form, source)
                self.assertEqual(unicodedata.normalize(form, once), once)


class TestUnicodeCanonicalIdentity(unittest.TestCase):
    """Case 6 · B — one logical path has exactly one security identity.

    Nothing in this class touches the filesystem. Both spellings are pushed
    through the path policy as strings, and the policy must answer identically
    for both: same canonical path, same read decision, same write decision.
    """

    def _pair(self, base):
        return (os.path.join(base, NFC_SOURCE), os.path.join(base, NFD_SOURCE))

    def _work_base(self):
        return os.path.join(path_policy.LEVEL1_ROOT, "work", SELFTEST_DIRNAME)

    def test_lexical_absolute_yields_one_identity(self):
        nfc, nfd = self._pair(self._work_base())
        self.assertEqual(path_policy.lexical_absolute(nfc),
                         path_policy.lexical_absolute(nfd))

    def test_normalize_yields_one_identity(self):
        nfc, nfd = self._pair(self._work_base())
        self.assertEqual(path_policy.normalize(nfc), path_policy.normalize(nfd))

    def test_the_canonical_form_is_nfc(self):
        import unicodedata
        for candidate in self._pair(self._work_base()):
            canonical = path_policy.normalize(candidate)
            self.assertEqual(unicodedata.normalize("NFC", canonical), canonical)

    def test_the_read_decision_is_the_same_for_both_spellings(self):
        nfc, nfd = self._pair(self._work_base())
        self.assertEqual(path_policy.assert_readable(nfc),
                         path_policy.assert_readable(nfd))

    def test_the_write_decision_is_the_same_for_both_spellings(self):
        nfc, nfd = self._pair(self._work_base())
        self.assertEqual(path_policy.assert_writable(nfc),
                         path_policy.assert_writable(nfd))

    def test_the_symlink_guard_returns_one_identity_for_both_spellings(self):
        nfc, nfd = self._pair(self._work_base())
        self.assertEqual(path_policy.assert_no_symlink_escape(nfc),
                         path_policy.assert_no_symlink_escape(nfd))

    def test_a_denied_root_denies_both_spellings_for_write(self):
        for base in (os.path.join(path_policy.PROJECT_ROOT, "authoring"),
                     path_policy.DISCOVERY_ROOT):
            for candidate in self._pair(base):
                with self.assertRaises(path_policy.PathPolicyError):
                    path_policy.assert_writable(candidate)

    def test_a_denied_root_denies_both_spellings_for_read(self):
        for candidate in self._pair("/etc"):
            with self.assertRaises(path_policy.PathPolicyError):
                path_policy.assert_readable(candidate)

    def test_no_normalization_collision_is_created(self):
        """Two spellings collapse to one path, never to two neighbours."""
        nfc, nfd = self._pair(self._work_base())
        canonical = {path_policy.normalize(nfc), path_policy.normalize(nfd)}
        self.assertEqual(len(canonical), 1)

    def test_no_case_collision_is_created_by_normalization(self):
        nfc, nfd = self._pair(self._work_base())
        a = path_policy.normalize(nfc)
        b = path_policy.normalize(nfd)
        self.assertEqual(a.lower(), b.lower())
        self.assertEqual(a, b)


class TestUnicodeFilesystemBehaviour(unittest.TestCase):
    """Case 6 · C — the operating system's real behaviour, accepted as found.

    Exactly one physical file is created. What macOS does with the second
    spelling is measured and recorded; it is not required to be anything. The
    security statement does not rest on it.
    """

    def setUp(self):
        self.dir, self.file = unicode_fixture()
        self.nfc_path = os.path.join(self.dir, NFC_SOURCE + ".txt")
        self.nfd_path = os.path.join(self.dir, NFD_SOURCE + ".txt")

    def _observe(self):
        if not os.path.lexists(self.nfd_path):
            return FS_NFD_NOT_ADDRESSABLE
        if os.path.samefile(self.nfc_path, self.nfd_path):
            return FS_SAME_OBJECT
        return FS_SEPARATE_ENTRIES

    def test_at_most_one_physical_file_was_created(self):
        entries = os.listdir(self.dir)
        self.assertEqual(len(entries), 1, entries)

    def test_the_observed_behaviour_is_recorded(self):
        observed = self._observe()
        self.assertIn(observed, FS_OBSERVATIONS, observed)
        record = os.path.join(
            path_policy.ensure_dir(
                os.path.join(path_policy.LEVEL1_ROOT, "work", SELFTEST_DIRNAME)),
            "unicode_fs_behaviour.txt")
        with open(path_policy.assert_writable(record), "w",
                  encoding="utf-8") as fh:
            fh.write("NFC_NFD_FILESYSTEM_BEHAVIOUR=%s\n" % observed)
        self.assertTrue(os.path.exists(record))

    def test_the_policy_treats_both_spellings_as_one_object(self):
        """True whatever the answer to `_observe` was. That is the point."""
        self.assertEqual(path_policy.normalize(self.nfc_path),
                         path_policy.normalize(self.nfd_path))
        self.assertEqual(path_policy.assert_readable(self.nfd_path),
                         path_policy.assert_readable(self.nfc_path))

    def test_two_directory_entries_are_not_required(self):
        self.assertEqual(len(os.listdir(self.dir)), 1)
        self.assertEqual(path_policy.assert_readable(self.nfc_path),
                         path_policy.assert_readable(self.nfd_path))

    def test_the_single_file_is_reachable_through_the_canonical_identity(self):
        canonical = path_policy.assert_readable(self.nfd_path)
        self.assertTrue(os.path.isfile(canonical), canonical)
        with open(canonical, "rb") as fh:
            self.assertEqual(fh.read(), b"unicode fixture\n")


class TestUnicodeSecurityRegression(unittest.TestCase):
    """Case 6 · D — normalization is not a bypass for any other control."""

    def setUp(self):
        self.dir, self.file = unicode_fixture()
        self.links = path_policy.ensure_dir(
            os.path.join(scratch(), "unicode_links"))

    def tearDown(self):
        for name in os.listdir(self.links):
            path = os.path.join(self.links, name)
            if os.path.lexists(path):
                os.unlink(path)

    def _link(self, name, target):
        path = os.path.join(self.links, name)
        if os.path.lexists(path):
            os.unlink(path)
        os.symlink(target, path)
        return path

    def _work_base(self):
        return os.path.join(path_policy.LEVEL1_ROOT, "work", SELFTEST_DIRNAME)

    def test_allowed_and_denied_cannot_split_across_the_two_spellings(self):
        """One logical path, one answer. Never allowed as NFC, denied as NFD."""
        bases = (self._work_base(),
                 os.path.join(path_policy.PROJECT_ROOT, "authoring"),
                 path_policy.DISCOVERY_ROOT,
                 "/etc")
        for base in bases:
            for check in (path_policy.assert_readable,
                          path_policy.assert_writable):
                results = []
                for name in (NFC_SOURCE, NFD_SOURCE):
                    try:
                        results.append(("ALLOW", check(os.path.join(base, name))))
                    except path_policy.PathPolicyError:
                        results.append(("DENY", None))
                self.assertEqual(results[0], results[1],
                                 "%s %s %r" % (base, check.__name__, results))

    def test_nfd_cannot_escape_an_nfc_allowlist(self):
        outside = os.path.join("/private/var", NFD_SOURCE)
        with self.assertRaises(path_policy.PathPolicyError):
            path_policy.assert_readable(outside)
        with self.assertRaises(path_policy.PathPolicyError):
            path_policy.assert_writable(outside)

    def test_normalization_does_not_bypass_the_symlink_guard(self):
        for name in (NFC_SOURCE, NFD_SOURCE):
            link = self._link(name + "_escape", "/etc")
            with self.assertRaises(path_policy.PathPolicyError) as ctx:
                path_policy.assert_no_symlink_escape(
                    os.path.join(link, "passwd"))
            self.assertIn("symlink component", str(ctx.exception))

    def test_a_symlink_named_in_one_form_is_caught_when_addressed_in_the_other(self):
        self._link(NFC_SOURCE + "_escape", "/etc")
        addressed = os.path.join(self.links, NFD_SOURCE + "_escape")
        with self.assertRaises(path_policy.PathPolicyError):
            path_policy.assert_no_symlink_escape(addressed)

    def test_normalization_does_not_bypass_parent_containment(self):
        for name in (NFC_SOURCE, NFD_SOURCE):
            escape = os.path.join(path_policy.LEVEL1_ROOT, name,
                                  "..", "..", "..", "etc")
            with self.assertRaises(path_policy.PathPolicyError):
                path_policy.assert_readable(escape)
            with self.assertRaises(path_policy.PathPolicyError):
                path_policy.assert_writable(escape)

    def test_normalization_cannot_produce_two_one_time_approval_identities(self):
        """An approval is keyed on (audit, phase, plan hash, target hash).

        `controller.assert_not_replayed` compares exactly that tuple. If the
        two spellings of one target produced two target hashes, one approval
        could be spent twice on the same file. They must not.
        """
        from automation import hashing
        identities = set()
        for name in (NFC_SOURCE, NFD_SOURCE):
            target = os.path.join(self.dir, name + ".txt")
            identities.add(("L1-A18", "RUN-A", "0" * 64,
                            hashing.sha256_file(target)))
        self.assertEqual(len(identities), 1, identities)

    def test_the_target_hash_is_identical_through_both_spellings(self):
        from automation import hashing
        nfc = hashing.sha256_file(os.path.join(self.dir, NFC_SOURCE + ".txt"))
        nfd = hashing.sha256_file(os.path.join(self.dir, NFD_SOURCE + ".txt"))
        self.assertTrue(hashing.is_hex64(nfc))
        self.assertEqual(nfc, nfd)

    def test_path_normalization_is_idempotent(self):
        for name in (NFC_SOURCE, NFD_SOURCE):
            candidate = os.path.join(self._work_base(), name)
            once = path_policy.normalize(candidate)
            self.assertEqual(path_policy.normalize(once), once)
            self.assertEqual(path_policy.lexical_absolute(once), once)

    def test_a_null_byte_is_still_rejected_in_both_spellings(self):
        for name in (NFC_SOURCE, NFD_SOURCE):
            with self.assertRaises(path_policy.PathPolicyError):
                path_policy.normalize(
                    os.path.join(self._work_base(), name + "\x00"))

    def test_a_relative_path_is_still_rejected_in_both_spellings(self):
        for name in (NFC_SOURCE, NFD_SOURCE):
            with self.assertRaises(path_policy.PathPolicyError):
                path_policy.assert_readable(os.path.join("work", name))


class TestCaseCollision(unittest.TestCase):
    """Case 7 — a case-only difference is reported, never silently accepted."""

    def test_case_variant_of_root_is_reported_not_silently_allowed(self):
        variant = path_policy.LEVEL1_ROOT.upper()
        if variant == path_policy.LEVEL1_ROOT:
            self.skipTest("root has no case variant")
        try:
            result = path_policy.assert_readable(variant)
        except path_policy.PathPolicyError as exc:
            self.assertIn("case", str(exc).lower())
        else:
            # On a case-insensitive volume realpath may return the true case.
            # Accepting it is fine; silently accepting a different directory is
            # not, so the result must still be inside the root.
            self.assertTrue(result.startswith(path_policy.LEVEL1_ROOT))


class TestUnexpectedWrite(unittest.TestCase):
    """Case 28 — a write outside LEVEL1_ROOT is refused at the policy layer."""

    def test_write_helpers_refuse_outside_level1(self):
        for candidate in (
            os.path.join(path_policy.PROJECT_ROOT, "authoring", "x.py"),
            os.path.join(path_policy.DISCOVERY_ROOT, "x.md"),
            "/tmp/x",
        ):
            with self.assertRaises(path_policy.PathPolicyError):
                path_policy.ensure_dir(candidate)

    def test_audit_dirs_are_inside_level1(self):
        for fn in (path_policy.audit_work_dir, path_policy.audit_results_dir,
                   path_policy.audit_evidence_dir):
            got = fn("L1-A01", "RUN-A")
            self.assertTrue(got.startswith(path_policy.LEVEL1_ROOT + os.sep))


class TestRootResolution(unittest.TestCase):
    """The roots come from paths.json and carry no hardcoded user name."""

    def test_all_three_roots_are_absolute_and_exist(self):
        for root in (path_policy.PROJECT_ROOT, path_policy.DISCOVERY_ROOT,
                     path_policy.LEVEL1_ROOT):
            self.assertTrue(os.path.isabs(root), root)
            self.assertTrue(os.path.isdir(root), root)

    def test_paths_json_holds_no_absolute_user_path(self):
        import json
        config = os.path.join(path_policy.LEVEL1_ROOT, "paths.json")
        with open(config, encoding="utf-8") as fh:
            data = json.load(fh)
        for key in ("project_root", "discovery_root", "level1_root"):
            self.assertFalse(data[key].startswith("/Users/"), key)

    def test_level1_root_is_the_only_write_root(self):
        self.assertEqual(path_policy.WRITE_ROOTS, (path_policy.LEVEL1_ROOT,))


def tearDownModule():
    root = os.path.join(path_policy.LEVEL1_ROOT, "work", SELFTEST_DIRNAME,
                        "path_policy")
    if os.path.isdir(root):
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
