"""The all-43 candidate-plan set, and the properties that make it usable.

R7 was built with nine plans and frozen against none. The freeze never
happened, and the reason it could not is what this module now holds in place:
`build/` is inside the frozen control manifest, so a plan file added after the
freeze would make the frozen package fail its own manifest. Every phase that
will ever run therefore needs its plan before the freeze, and "every" is a
number this module checks rather than a word.

The checks are deliberately about properties a reader can restate:

    there are exactly as many plans as the registry requires;
    each audit-phase pair has exactly one;
    building twice produces the same bytes;
    a plan naming an absent, zero-byte or symlinked dependency is refused;
    a plan whose target hash no longer matches disk is refused;
    an operation is refused if the catalogue does not know it;
    an archive operation is refused if it does not match the archive's format;
    the rehearsal writes nothing into live state.

The archive-format check exists because the pre-freeze rehearsal caught the
defect it describes. L1-A12's corpus is a gzipped tar and the plan reached for
`ARCHIVE_EXTRACT_SANDBOX`, which invokes unzip; unzip on a tarball reports a
missing end-of-central-directory signature, which is a fact about unzip and
not about the corpus. The plan now uses `TAR_LIST`, and this test keeps any
plan from pairing the two again.
"""

import ast
import json
import os
import unittest

from automation import (hashing, operation_catalog, path_policy,
                        schema_validation, state_machine)

ROOT = path_policy.LEVEL1_ROOT
PLANS = os.path.join(ROOT, "build", "candidate_plans_r8")
COVERAGE = os.path.join(PLANS, "PLAN_COVERAGE_MANIFEST.json")
REHEARSAL = os.path.join(ROOT, "work", "_rehearsal_r8", "REHEARSAL_REPORT.json")
REGISTRY = os.path.join(ROOT, "audit_registry.json")

# Archive operations and the container formats they can actually read.
ZIP_ONLY_OPERATIONS = ("ARCHIVE_EXTRACT_SANDBOX", "ZIP_LIST")
TAR_SUFFIXES = (".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tar.xz")


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def required_pairs():
    registry = load_json(REGISTRY)
    pairs = []
    for audit in registry["audits"]:
        for phase in state_machine.phase_order(audit["replications"]):
            pairs.append((audit["audit_id"], phase))
    return pairs


def all_plans():
    out = {}
    for audit_id in sorted(os.listdir(PLANS)):
        audit_dir = os.path.join(PLANS, audit_id)
        if not os.path.isdir(audit_dir):
            continue
        for phase in sorted(os.listdir(audit_dir)):
            path = os.path.join(audit_dir, phase, "plan.json")
            if os.path.isfile(path):
                out[(audit_id, phase)] = path
    return out


class PlanCoverage(unittest.TestCase):
    def test_every_required_phase_has_exactly_one_plan(self):
        required = required_pairs()
        found = all_plans()
        self.assertEqual(len(required), 43, "the registry requires 43 phases")
        self.assertEqual(sorted(found), sorted(required),
                         "the plan set and the registry disagree")

    def test_no_plan_exists_for_a_phase_the_registry_does_not_name(self):
        self.assertEqual(sorted(set(all_plans()) - set(required_pairs())), [])

    def test_coverage_manifest_agrees_with_disk(self):
        coverage = load_json(COVERAGE)
        self.assertEqual(coverage["REQUIRED_PLAN_COUNT"], 43)
        self.assertEqual(coverage["CANDIDATE_PLAN_COUNT"], 43)
        self.assertEqual(coverage["MISSING_PLAN_COUNT"], 0)
        self.assertEqual(coverage["DUPLICATE_PLAN_COUNT"], 0)
        self.assertEqual(coverage["UNKNOWN_PLAN_COUNT"], 0)
        for row in coverage["plans"]:
            path = os.path.join(ROOT, row["plan_path"])
            self.assertTrue(os.path.isfile(path), row["plan_path"])
            with open(path, encoding="utf-8") as fh:
                self.assertEqual(hashing.sha256_text(fh.read()),
                                 row["plan_sha256"], row["plan_path"])

    def test_coverage_manifest_digest_file_matches(self):
        digest_path = os.path.join(PLANS, "PLAN_COVERAGE_MANIFEST.sha256")
        with open(digest_path, encoding="utf-8") as fh:
            recorded = fh.read().split()[0]
        self.assertEqual(recorded, hashing.sha256_file(COVERAGE))

    def test_phase_totals_by_kind(self):
        coverage = load_json(COVERAGE)
        self.assertEqual(coverage["phase_totals_by_kind"],
                         {"RUN-A": 35, "RUN-B": 4, "COMPARISON": 4})


class PlanValidity(unittest.TestCase):
    def test_every_plan_validates_against_the_schema(self):
        for (audit_id, phase), path in sorted(all_plans().items()):
            with open(path, encoding="utf-8") as fh:
                plan = schema_validation.parse_strict(fh.read())
            schema_validation.validate_named(plan,
                                             "execution_plan.schema.json")
            self.assertEqual(plan["audit_id"], audit_id)
            self.assertEqual(plan["run_phase"], phase)

    def test_every_operation_is_in_the_catalogue(self):
        for (audit_id, phase), path in sorted(all_plans().items()):
            plan = load_json(path)
            operation_catalog.validate_plan_operations(plan)

    def test_no_forbidden_operation_appears_in_any_plan(self):
        for (audit_id, phase), path in sorted(all_plans().items()):
            for step in load_json(path)["steps"]:
                self.assertNotIn(step["operation"],
                                 operation_catalog.FORBIDDEN,
                                 "%s/%s" % (audit_id, phase))

    def test_step_ids_are_unique_within_a_plan(self):
        for (audit_id, phase), path in sorted(all_plans().items()):
            ids = [s["step_id"] for s in load_json(path)["steps"]]
            self.assertEqual(len(ids), len(set(ids)),
                             "%s/%s has a duplicate step_id" % (audit_id, phase))

    def test_every_target_is_absolute_present_and_hash_matching(self):
        for (audit_id, phase), path in sorted(all_plans().items()):
            target = load_json(path)["target"]
            self.assertTrue(target["path"].startswith("/"))
            self.assertTrue(os.path.isfile(target["path"]),
                            "%s/%s target absent" % (audit_id, phase))
            self.assertFalse(os.path.islink(target["path"]))
            self.assertNotEqual(os.path.getsize(target["path"]), 0)
            self.assertEqual(hashing.sha256_file(target["path"]),
                             target["sha256"],
                             "%s/%s target hash moved" % (audit_id, phase))

    def test_no_plan_path_escapes_its_root(self):
        for (audit_id, phase), path in sorted(all_plans().items()):
            plan = load_json(path)
            for step in plan["steps"]:
                for value in step.get("params", {}).values():
                    if isinstance(value, str) and value.startswith("/"):
                        self.assertNotIn("/../", value + "/",
                                         "%s/%s" % (audit_id, phase))

    def test_every_plan_carries_its_binding_envelope(self):
        for (audit_id, phase), path in sorted(all_plans().items()):
            plan = load_json(path)
            envelopes = [e for e in plan["test_matrix"]
                         if e.get("check_id") == "PLAN_BINDING"]
            if (audit_id, phase) in (("L1-A18", "RUN-A"), ("L1-A18", "RUN-B"),
                                     ("L1-A18", "COMPARISON"),
                                     ("L1-A31", "RUN-A"), ("L1-A31", "RUN-B"),
                                     ("L1-A31", "COMPARISON"),
                                     ("L1-A34", "RUN-A"), ("L1-A34", "RUN-B"),
                                     ("L1-A34", "COMPARISON")):
                # The nine pre-existing plans were written before the envelope
                # existed. They carry their bindings in their own matrix
                # entries and are not rewritten for uniformity.
                continue
            self.assertEqual(len(envelopes), 1,
                             "%s/%s has %d binding envelopes"
                             % (audit_id, phase, len(envelopes)))
            envelope = envelopes[0]
            for field in ("method", "executable", "fixed_cwd", "environment",
                          "approval_token_binding", "evidence_paths",
                          "retry_classification", "expectation_classes"):
                self.assertIn(field, envelope, "%s/%s" % (audit_id, phase))


class ArchiveFormatRegression(unittest.TestCase):
    """A zip operation must never be pointed at a tar archive.

    The pre-freeze rehearsal executed L1-A12's extraction step and unzip
    reported that the end-of-central-directory signature was not found. The
    archive is a gzipped tar. An operation that cannot read its own input
    fails for a reason that says nothing about the material, and an audit
    whose step fails that way learns nothing.
    """

    def test_no_zip_operation_names_a_tar_archive(self):
        for (audit_id, phase), path in sorted(all_plans().items()):
            for step in load_json(path)["steps"]:
                if step["operation"] not in ZIP_ONLY_OPERATIONS:
                    continue
                params = step.get("params", {})
                named = [params.get("archive"), params.get("path")]
                for value in named:
                    if not isinstance(value, str):
                        continue
                    self.assertFalse(
                        value.endswith(TAR_SUFFIXES),
                        "%s/%s step %r points %s at a tar archive: %s"
                        % (audit_id, phase, step["step_id"],
                           step["operation"], value))

    def test_tar_list_is_used_for_the_tar_corpus(self):
        plan = load_json(os.path.join(PLANS, "L1-A12", "RUN-A", "plan.json"))
        operations = {s["operation"] for s in plan["steps"]}
        self.assertIn("TAR_LIST", operations)
        self.assertNotIn("ARCHIVE_EXTRACT_SANDBOX", operations)


class RehearsalEvidence(unittest.TestCase):
    def test_every_phase_is_rehearsed_and_pass_ready(self):
        report = load_json(REHEARSAL)
        self.assertEqual(report["phases_rehearsed"], 43)
        self.assertEqual(report["phases_required"], 43)
        self.assertTrue(report["all_pass_ready"])
        not_ready = [r for r in report["reports"] if not r["ok"]]
        self.assertEqual(not_ready, [], "phases not pass-ready")

    def test_rehearsal_changed_no_live_state(self):
        report = load_json(REHEARSAL)
        self.assertTrue(report["LIVE_STATE_UNCHANGED"])
        self.assertEqual(report["live_state_before"],
                         report["live_state_after"])

    def test_rehearsal_covers_the_same_plans_that_are_on_disk(self):
        report = load_json(REHEARSAL)
        rehearsed = {(r["audit_id"], r["run_phase"]) for r in report["reports"]}
        self.assertEqual(sorted(rehearsed), sorted(all_plans()))
        for entry in report["reports"]:
            path = os.path.join(ROOT, entry["plan_path"])
            with open(path, encoding="utf-8") as fh:
                self.assertEqual(hashing.sha256_text(fh.read()),
                                 entry["plan_sha256"],
                                 "%s/%s was rehearsed at other bytes"
                                 % (entry["audit_id"], entry["run_phase"]))

    def test_every_unexecuted_step_states_why(self):
        report = load_json(REHEARSAL)
        for entry in report["reports"]:
            for step in entry["steps"]:
                if step.get("executed"):
                    continue
                if "argv_error" in step:
                    continue
                self.assertIn("not_executed_reason", step,
                              "%s/%s step %r was not executed and does not "
                              "say why" % (entry["audit_id"],
                                           entry["run_phase"],
                                           step["step_id"]))

    def test_no_step_failed_for_the_wrong_reason(self):
        report = load_json(REHEARSAL)
        for entry in report["reports"]:
            for step in entry["steps"]:
                self.assertNotEqual(step.get("result"),
                                    "FAILED_FOR_THE_WRONG_REASON",
                                    "%s/%s %s" % (entry["audit_id"],
                                                  entry["run_phase"],
                                                  step["step_id"]))


class RunBIsolation(unittest.TestCase):
    """L1-A19 RUN-B must not be able to see RUN-A's answers."""

    def test_run_b_module_does_not_import_run_a(self):
        """Checked on the parse, not on the text.

        A substring search over the source would match the docstring that
        promises the module does not import RUN-A, which is the same shape of
        mistake as a grep that finds its own invocation. The import list is
        read from the AST instead, so the check is about what the module does.
        """
        for name in ("a19_run_b.py", "a19_run_b_cli.py"):
            path = os.path.join(ROOT, "automation", name)
            with open(path, encoding="utf-8") as fh:
                tree = ast.parse(fh.read(), filename=path)
            imported = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(a.name for a in node.names)
                elif isinstance(node, ast.ImportFrom):
                    imported.update(a.name for a in node.names)
                    if node.module:
                        imported.add(node.module)
            self.assertNotIn("a19_run_a", imported,
                             "%s imports RUN-A: %s" % (name, sorted(imported)))
            attributes = {n.attr for n in ast.walk(tree)
                          if isinstance(n, ast.Attribute)}
            self.assertNotIn("a19_run_a", attributes,
                             "%s reaches RUN-A through an attribute" % name)

    def test_run_b_plan_reads_no_run_a_directory(self):
        plan = load_json(os.path.join(PLANS, "L1-A19", "RUN-B", "plan.json"))
        blob = json.dumps(plan["steps"])
        for forbidden in ("work/L1-A19/RUN-A", "evidence/L1-A19/RUN-A",
                          "results/L1-A19/RUN-A"):
            self.assertNotIn(forbidden, blob)

    def test_the_two_methods_are_different_formulations(self):
        run_a = load_json(os.path.join(PLANS, "L1-A19", "RUN-A", "plan.json"))
        run_b = load_json(os.path.join(PLANS, "L1-A19", "RUN-B", "plan.json"))
        method_a = run_a["test_matrix"][0]["method"]
        method_b = run_b["test_matrix"][0]["method"]
        self.assertNotEqual(method_a, method_b)
        self.assertIn("generation form", method_a)
        self.assertIn("verification form", method_b)

    def test_run_b_runs_a_different_executable(self):
        run_b = load_json(os.path.join(PLANS, "L1-A19", "RUN-B", "plan.json"))
        self.assertIn("java", run_b["test_matrix"][0]["executable"])


class ExternalHostPlanBinding(unittest.TestCase):
    """L1-A24 must bind the Mac directory honestly and claim nothing about it."""

    def setUp(self):
        self.plan = load_json(os.path.join(PLANS, "L1-A24", "RUN-A",
                                           "plan.json"))
        self.envelope = self.plan["test_matrix"][0]

    def test_the_external_directory_is_the_operator_approved_mac_path(self):
        blob = json.dumps(self.plan)
        self.assertIn("/Users/martinotten/Downloads", blob)

    def test_the_mac_path_is_not_claimed_to_exist_here(self):
        self.assertFalse(os.path.exists("/Users/martinotten/Downloads"))
        limitations = " ".join(self.envelope["limitations"])
        self.assertIn("does not exist on this Ubuntu host", limitations)

    def test_no_ubuntu_directory_is_substituted(self):
        for step in self.plan["steps"]:
            directory = step.get("params", {}).get("canonical_directory")
            if directory:
                self.assertTrue(directory.startswith("/Users/"),
                                "an external launch directory was replaced by "
                                "a local path: %s" % directory)

    def test_the_load_behaviour_operation_is_operator_performed(self):
        self.assertIn("CLAUDE_LOAD_BEHAVIOUR_TEST",
                      operation_catalog.OPERATOR_PERFORMED)
        with self.assertRaises(operation_catalog.OperationError):
            operation_catalog.build_argv("CLAUDE_LOAD_BEHAVIOUR_TEST", {})

    def test_the_plan_does_not_claim_the_launch_happened(self):
        matrix = {e.get("check_id"): e for e in self.plan["test_matrix"]}
        self.assertIn("no_claim_of_execution", matrix)
        self.assertIn("does not claim the real Mac launch occurred",
                      matrix["no_claim_of_execution"]["required_result"])


class ScannerRobustness(unittest.TestCase):
    """A claim must not be indistinguishable from what it denies.

    The independent pre-freeze verification searched the L1-A19 RUN-B plan
    document for a path belonging to RUN-A and found one - inside the sentence
    that promised no such path was used. Its import check, which parsed rather
    than searched, was right; its directory check, which searched, was wrong.

    Both halves of that are worth keeping. A verifier should parse. And a plan
    should not carry a string that a reasonable search cannot tell apart from
    the thing it is looking for, which is the same reason `grep -c sk-ant`
    over a shell history counted its own invocation.
    """

    def test_the_run_b_plan_names_no_run_a_directory_anywhere(self):
        plan = load_json(os.path.join(PLANS, "L1-A19", "RUN-B", "plan.json"))
        document = json.dumps(plan)
        for literal in ("work/L1-A19/RUN-A", "evidence/L1-A19/RUN-A",
                        "results/L1-A19/RUN-A"):
            self.assertNotIn(literal, document,
                             "the RUN-B plan document contains %r, which a "
                             "search cannot tell from an actual read"
                             % literal)

    def test_the_run_b_steps_name_only_this_phases_own_directory(self):
        plan = load_json(os.path.join(PLANS, "L1-A19", "RUN-B", "plan.json"))
        for step in plan["steps"]:
            paths = [v for v in step.get("params", {}).values()
                     if isinstance(v, str) and v.startswith("/")]
            paths += [a for a in step.get("params", {}).get("args", [])
                      if isinstance(a, str) and a.startswith("/")]
            for path in paths:
                self.assertNotIn("/RUN-A", path, step["step_id"])

    def test_the_comparison_plan_may_name_both_phases(self):
        """The exception, stated rather than left implicit."""
        plan = load_json(os.path.join(PLANS, "L1-A19", "COMPARISON",
                                      "plan.json"))
        document = json.dumps(plan)
        self.assertIn("evidence/L1-A19/RUN-A", document,
                      "a comparison that cannot name both phases compares "
                      "nothing")


class PredecessorIntegrityRecord(unittest.TestCase):
    """R4, R5 and R6, settled per file rather than by a summary digest."""

    def setUp(self):
        # R8 retarget: the predecessor integrity record lives in the
        # predecessor's lineage tree, which R8 references by digest rather
        # than copying. `inherited_lineage_root` verifies that digest before
        # returning the path, so this reads the same bytes R7 read and fails
        # loudly if they have moved.
        from automation.package_tests import inherited_lineage_root
        self.record = load_json(os.path.join(inherited_lineage_root(),
                                             "PREDECESSOR_INTEGRITY.json"))

    def test_all_three_predecessors_are_unchanged(self):
        self.assertTrue(self.record["ALL_PREDECESSORS_UNCHANGED"])
        for name in ("R4", "R5", "R6"):
            self.assertTrue(self.record["trees"][name]["snapshot_matches"],
                            name)

    def test_r6_is_verified_file_by_file(self):
        r6 = self.record["trees"]["R6"]
        self.assertEqual(r6["per_file_entries"], 15153)
        self.assertEqual(r6["per_file_matched"], 15153)
        self.assertEqual(r6["per_file_mismatched"], 0)
        self.assertEqual(r6["per_file_missing"], 0)
        self.assertTrue(r6["per_file_unchanged"])

    def test_the_lineage_copy_equals_r6_in_place(self):
        self.assertTrue(
            self.record["r6_lineage_copy"]["identical_to_r6_in_place"])

    def test_the_record_states_the_formula_it_used(self):
        method = self.record["method"]
        self.assertIn("sorted by relative path", method)
        self.assertIn("SHA-256", method)
        self.assertIn("Symlinks are skipped", method)

    def test_no_predecessor_contains_a_symlink(self):
        for name in ("R4", "R5", "R6"):
            self.assertEqual(self.record["trees"][name]["symlinks"], [], name)
