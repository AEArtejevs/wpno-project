"""Machine-checkable expectations for every control-role step.

Why this file exists.

The R7 repair measured that 55 of 307 steps carry a control role and declare
no `expected_exit_code`, and recorded that finding as NOT ADJUDICATED: not
assumed all defective, not assumed all benign. This is the adjudication.

What the measurement actually showed, once each of the 55 was read rather
than counted:

  119   steps carry a control role (POSITIVE, NEGATIVE, MUTATION, ORACLE)
   64   already declare `expected_exit_code`
   55   do not
   41   of those 55 declare some other expectation -- `expected_result`,
        `required_result`, `expected_failure_reason` -- in prose
   14   declare no expectation of any kind

Prose is not an expectation a harness can check. The frozen `judge()` says so
itself: "asserting it by substring would be a check that passes on wording".
So a step with `expected_result: "ZERO_HITS"` and nothing else was, to the
harness, a step with no expectation at all -- scored `ok` if it exited 0,
which for a control built to fail is the wrong polarity, and for a control
built to find nothing says nothing about whether it looked.

Every one of the 119 therefore gets an expectation here that the harness can
evaluate against what the operation actually returns.

The rule used to choose it, and the line it refuses to cross.

  Where the plan already states a determinate outcome -- "ZERO_HITS",
  "DIGESTS_DIFFER", "CONFIRMED", "CONTRADICTED" -- that outcome is bound to
  the field the operation actually measures. `total_matches`, `equal`,
  `identical`, `exists`. The expectation is then checked against a number or
  a boolean the run produced, not against a sentence.

  Where the plan deliberately leaves the outcome open -- L1-A02's three
  modified-document fixtures say "Expected: open" in as many words, and
  L1-A01's determinism control exists to find out whether two runs agree --
  no outcome is invented. Writing one down would be manufacturing an
  expected result, which is forbidden, and it would make the control pass by
  construction. What is demanded instead is
  `expected_status: COMPLETED_OUTCOME_IS_SUBSTANTIVE`: the step must really
  have run and produced an exit code and evidence. That is not a weaker
  check. It is the exact check whose absence let 165 steps report success
  having executed nothing, and no skipped step can satisfy it.

Two entries carry `degenerate_operands`. L1-A28's
`recalculate_digest_independently` and L1-A33's `declared_versus_actual` both
compare a file with itself: `left` and `right` are the same path, so `equal`
is true by construction and an expectation bound to it would be a control
that cannot fail. That is a defect in those two steps and it is recorded as
one rather than papered over with an expectation that always holds. It is
outside the two plan repairs authorised for R8, so the steps are not changed;
they are bound to "the comparison must complete" and the finding is carried
into CONTROL_EXPECTATION_COVERAGE.json for the human.

One entry carries `assertion_not_expressible_in_step`, for the same reason
and with the same disposition.
"""

# expected_status
SUBSTANTIVE = "COMPLETED_OUTCOME_IS_SUBSTANTIVE"

# The table. Keyed by (audit_id, run_phase, step_id).
#
# `why` is not decoration: it is the record of what the step was read to mean
# before an expectation was attached to it, so a reader can disagree with the
# reading rather than only with the result.
EXPECTATIONS = {
    ("L1-A01", "RUN-A", "independent_container_read"): {
        "expected_exit_code": 0,
        "why": ("An oracle that cannot read the container is an "
                "infrastructure failure, not a finding. The entry list it "
                "returns is substantive."),
    },
    ("L1-A01", "RUN-A", "positive_control_known_input_difference"): {
        "expected_exit_code": 0, "expected_hash_relation": "DIFFERENT",
        "why": ("A difference was introduced deliberately. If the digests "
                "match, the comparison is not reading both operands."),
    },
    ("L1-A01", "RUN-A", "negative_control_same_input_twice"): {
        "expected_status": SUBSTANTIVE,
        "why": ("Whether two runs of the same input agree is the audit's "
                "question about determinism. Binding EQUAL here would write "
                "down the answer before measuring it."),
    },
    ("L1-A01", "RUN-A", "mutation_control_pin_nondeterminism"): {
        "expected_status": SUBSTANTIVE,
        "why": ("The plan states both outcomes as informative: deterministic "
                "means environmental, still varying means in the code."),
    },
    ("L1-A02", "RUN-A", "run_f5"): {
        "expected_status": SUBSTANTIVE,
        "why": "The plan says 'Expected: open' for this fixture.",
    },
    ("L1-A02", "RUN-A", "run_f6"): {
        "expected_status": SUBSTANTIVE,
        "why": "The plan says 'Expected: open' for this fixture.",
    },
    ("L1-A02", "RUN-A", "run_f9"): {
        "expected_status": SUBSTANTIVE,
        "why": "The plan says 'Expected: open' for this fixture.",
    },
    ("L1-A02", "RUN-A", "independent_reader"): {
        "expected_exit_code": 0, "expected_boolean": True,
        "why": ("The oracle must parse the document. What it finds in it is "
                "substantive."),
    },
    ("L1-A03", "RUN-A", "positive_control_unique_string"): {
        "expected_exit_code": 0, "expected_minimum_count": 1,
        "why": ("A positive control for a string known to be present must "
                "find it at least once. Zero hits would mean the scan is not "
                "reading the tree."),
    },
    ("L1-A03", "RUN-A", "negative_control_absent_identifier"): {
        "expected_exit_code": 0, "expected_count": 0,
        "why": ("ZERO_HITS, as the plan states. The scan must complete and "
                "find nothing; an exit code alone could not tell that apart "
                "from never having scanned."),
    },
    ("L1-A04", "RUN-A", "generate_t2"): {
        "expected_exit_code": 0,
        "why": ("This generates the mutated fixture the later checks read. "
                "Generation must succeed; what the document then contains is "
                "substantive."),
    },
    ("L1-A04", "RUN-A", "generate_t4"): {
        "expected_exit_code": 0, "why": "As generate_t2.",
    },
    ("L1-A04", "RUN-A", "generate_t6"): {
        "expected_exit_code": 0, "why": "As generate_t2.",
    },
    ("L1-A04", "RUN-A", "extract_real_headings"): {
        "expected_exit_code": 0, "expected_boolean": True,
        "why": "The oracle must parse the generated document.",
    },
    ("L1-A04", "RUN-A", "extract_toc_entries"): {
        "expected_exit_code": 0, "expected_boolean": True,
        "why": "The oracle must parse the generated document.",
    },
    ("L1-A06", "RUN-A", "count_rules_evaluated"): {
        "expected_exit_code": 0,
        "why": ("The instrumented copy must run. The plan is explicit that "
                "zero rules with exit 0 is a FAIL, so the count is the "
                "finding and is not bound here."),
    },
    ("L1-A08", "RUN-A", "mutation_control_specificity"): {
        "expected_status": SUBSTANTIVE,
        "why": ("Whether the altered cases stop matching is what the control "
                "measures. The guard's exit code has not been measured to "
                "encode that, and binding one would be an assumption."),
    },
    ("L1-A10", "RUN-A", "positive_control_unique_string"): {
        "expected_exit_code": 0, "expected_minimum_count": 1,
        "why": "A string known to be present must be found at least once.",
    },
    ("L1-A10", "RUN-A", "negative_control_absent_identifier"): {
        "expected_exit_code": 0, "expected_count": 0,
        "why": "ZERO_HITS, as the plan states.",
    },
    ("L1-A11", "RUN-A", "mutation_control_one_character"): {
        "expected_status": SUBSTANTIVE,
        "why": ("Whether the altered entry moves from matched to differing "
                "is the measurement; it is read from the comparison output, "
                "not from an exit code."),
    },
    ("L1-A12", "RUN-A", "read_label_derivation"): {
        "expected_exit_code": 0, "expected_boolean": True,
        "why": "The oracle's provenance record must parse.",
    },
    ("L1-A12", "RUN-A", "mutation_control_narrow_one_pattern"): {
        "expected_status": SUBSTANTIVE,
        "why": ("Whether the attributed false-positive count falls is read "
                "from the narrowed run's output."),
    },
    ("L1-A13", "RUN-A", "mutation_control_outside_senate_set"): {
        "expected_status": SUBSTANTIVE,
        "why": ("The control distinguishes 'passed' from 'never examined', "
                "which is a distinction in the output and not in the exit "
                "code."),
    },
    ("L1-A14", "RUN-A", "parse_document_xml"): {
        "expected_exit_code": 0, "expected_boolean": True,
        "why": "The oracle must parse word/document.xml.",
    },
    ("L1-A14", "RUN-A", "independent_citation_enumeration"): {
        "expected_exit_code": 0,
        "why": ("The independent enumeration must run. Its counts are the "
                "oracle's answer and are substantive."),
    },
    ("L1-A14", "RUN-A", "mutation_control_removed_citation"): {
        "expected_status": SUBSTANTIVE,
        "why": ("The count must fall by exactly one, which is read from the "
                "counts file the run writes."),
    },
    ("L1-A16", "RUN-A", "independent_rendered_text"): {
        "expected_exit_code": 0, "expected_boolean": True,
        "why": "The oracle must parse the case document.",
    },
    ("L1-A16", "RUN-A", "mutation_control_payload_altered"): {
        "expected_status": SUBSTANTIVE,
        "why": "As L1-A08's specificity control.",
    },
    ("L1-A17", "RUN-A", "positive_control_known_invocation"): {
        "expected_exit_code": 0, "expected_minimum_count": 1,
        "why": "AT_LEAST_ONE_INVOCATION_LOCATED, as the plan states.",
    },
    ("L1-A17", "RUN-A", "negative_control_absent_identifier"): {
        "expected_exit_code": 0, "expected_count": 0,
        "why": "ZERO_HITS, as the plan states.",
    },
    ("L1-A20", "RUN-A", "positive_control_identical_pair"): {
        "expected_exit_code": 0, "expected_boolean": True,
        "expected_difference_count": 0,
        "why": ("EQUAL_AT_EVERY_LEVEL. Two copies known to be identical must "
                "compare identical and differ in zero bytes."),
    },
    ("L1-A20", "RUN-A", "negative_control_differing_pair"): {
        "expected_exit_code": 0, "expected_boolean": False,
        "why": ("UNEQUAL_AT_THE_RAW_LEVEL. The comparison must complete and "
                "report the two files as not identical."),
    },
    ("L1-A20", "RUN-A", "mutation_control_comment_only"): {
        "expected_exit_code": 0, "expected_boolean": True,
        "why": ("The AST of a copy differing only in a comment must parse. "
                "Whether the ASTs are equal is compared downstream."),
    },
    ("L1-A21", "RUN-A", "positive_control_export_names_expected_service"): {
        "expected_exit_code": 0, "expected_boolean": True,
        "why": ("The index must parse, and `expect_contains` is enforced by "
                "the handler, which fails the operation if the name is "
                "absent."),
    },
    ("L1-A21", "RUN-A", "negative_control_export_is_not_another_project"): {
        "expected_exit_code": 0, "expected_count": 0,
        "why": ("R8 repair. The step now counts the foreign-project marker "
                "in the plain-text listing instead of handing it to a JSON "
                "parser that refused it before the assertion was reached."),
    },
    ("L1-A22", "RUN-A", "negative_control_unmatched_name"): {
        "expected_exit_code": "NONZERO",
        "why": ("A file matching no collection pattern must not be "
                "collected, and pytest does not exit 0 when it collects "
                "nothing. The exit code is asserted rather than the wording "
                "of the message."),
    },
    ("L1-A23", "RUN-A", "read_mac_reality"): {
        "expected_exit_code": 0, "expected_boolean": True,
        "why": "The operator-produced Mac evidence must parse.",
    },
    ("L1-A23", "RUN-A", "positive_control_true_claim"): {
        "expected_exit_code": 0, "expected_boolean": True,
        "why": ("CONFIRMED: a path constructed true by this audit must be "
                "reported as existing."),
    },
    ("L1-A23", "RUN-A", "negative_control_false_claim"): {
        "expected_exit_code": 0, "expected_boolean": False,
        "why": ("CONTRADICTED: a path constructed false by this audit must "
                "be reported as not existing. STAT_FILE returns exit 0 with "
                "exists false by design -- absence is the measurement here, "
                "not an error -- so the boolean is what carries the control "
                "and an exit code alone would not."),
    },
    ("L1-A24", "RUN-A", "external_launch_inside_project"): {
        "expected_status": "OPERATOR_ACTION",
        "why": ("The operation is performed on another host under an "
                "approval bound to an execution packet. The expectation this "
                "machine can check is that it was recorded as an operator "
                "action and never performed here."),
    },
    ("L1-A24", "RUN-A", "negative_control_impossible_file"): {
        "expected_exit_code": 0, "expected_boolean": True,
        "corrected_annotation": (
            "An earlier revision of this table recorded that the control's "
            "assertion was not expressible by its step. That was wrong, and "
            "it was wrong in the direction that matters: it described a real "
            "check as an absent one. The step does carry "
            "`expect_absent: \"a_file_that_cannot_apply\"`, and "
            "PARSE_JSON_READONLY enforces it -- the handler fails the "
            "operation if the string is present anywhere in the document "
            "text. The assertion is therefore machine-checked, and the "
            "expectation below adds that the record must also parse."),
        "why": ("The intake record must parse, and `expect_absent` is "
                "enforced by the handler: an impossible file reported as "
                "loaded fails the operation rather than being noted."),
    },
    ("L1-A24", "RUN-A", "mutation_control_write_topology"): {
        "expected_exit_code": 0, "expected_hash_relation": "EQUAL",
        "why": ("The external directory's pre-run and post-run manifests "
                "must be equal: the redirection is in force exactly when the "
                "external directory did not change."),
    },
    ("L1-A27", "RUN-A", "negative_control_two_files_differ"): {
        "expected_exit_code": 0, "expected_hash_relation": "DIFFERENT",
        "why": ("DIGESTS_DIFFER. Equality would mean the comparison is not "
                "reading both operands, which is what the plan already says."),
    },
    ("L1-A27", "RUN-A", "mutation_control_one_byte"): {
        "expected_exit_code": 0, "expected_boolean": False,
        "why": ("One deliberately altered byte must make the archives "
                "compare as not identical. Zero detected differences is a "
                "measurement error, not a pass -- CLAUDE.md section 6."),
    },
    ("L1-A28", "RUN-A", "recalculate_digest_independently"): {
        "expected_exit_code": 0,
        "degenerate_operands": (
            "left and right name the same path, so `equal` is true by "
            "construction. No outcome expectation is bound to it, because a "
            "control that cannot fail is not a control. Outside the two plan "
            "repairs authorised for R8; recorded for the human."),
        "why": "The recalculation must complete.",
    },
    ("L1-A28", "RUN-A", "negative_control_different_input"): {
        "expected_exit_code": 0, "expected_hash_relation": "DIFFERENT",
        "why": "DIGESTS_DIFFER, as the plan states.",
    },
    ("L1-A28", "RUN-A", "mutation_control_content_byte"): {
        "expected_exit_code": 0, "expected_boolean": False,
        "why": "One altered content byte must change the comparison.",
    },
    ("L1-A29", "RUN-A", "negative_control_two_files_differ"): {
        "expected_exit_code": 0, "expected_hash_relation": "DIFFERENT",
        "why": "DIGESTS_DIFFER, as the plan states.",
    },
    ("L1-A29", "RUN-A", "mutation_control_one_byte"): {
        "expected_exit_code": 0, "expected_boolean": False,
        "why": "One altered byte must be detected.",
    },
    ("L1-A30", "RUN-A", "mutation_control_added_entry"): {
        "expected_exit_code": 0, "expected_minimum_count": 1,
        "why": ("The archive with the added entry must list at least one "
                "entry. Which of them is the AppleDouble entry is counted "
                "downstream; ZIP_LIST's own count is of all entries, so "
                "binding an exact number here would assert something the "
                "operation does not measure."),
    },
    ("L1-A33", "RUN-A", "declared_versus_actual"): {
        "expected_exit_code": 0,
        "degenerate_operands": (
            "left and right name the same path, as in L1-A28. No outcome "
            "expectation is bound. Recorded for the human."),
        "why": "The comparison must complete.",
    },
    ("L1-A33", "RUN-A", "negative_control_altered_entry"): {
        "expected_exit_code": 0, "expected_boolean": False,
        "why": "MISMATCH_REPORTED: the altered entry must not compare equal.",
    },
    ("L1-A33", "RUN-A", "mutation_control_altered_declaration"): {
        "expected_exit_code": 0, "expected_boolean": False,
        "why": ("The declaration side must be live: an altered declared hash "
                "must produce a mismatch too."),
    },
    ("L1-A35", "RUN-A", "positive_control_byte_preserving_copy"): {
        "expected_exit_code": 0, "expected_boolean": True,
        "expected_difference_count": 0,
        "why": "EQUAL_AT_EVERY_LAYER, as the plan states.",
    },
    ("L1-A35", "RUN-A", "negative_control_recompressing_copy"): {
        "expected_exit_code": 0, "expected_boolean": False,
        "why": ("CONTAINER_LAYER_DIFFERS: recompression rewrites the "
                "container, so the two containers must not compare "
                "identical."),
    },
}


def for_step(audit_id, run_phase, step_id):
    return EXPECTATIONS.get((audit_id, run_phase, step_id))
