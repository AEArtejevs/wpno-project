"""Audit state machine.

Transitions are explicit and total: a transition not listed cannot occur. The
alternative — inferring the next state from whatever files happen to exist —
is how a run resumes into a state nobody intended.
"""

STATES = (
    "NOT_STARTED",
    "PLANNING",
    "PLAN_READY",
    "AWAITING_APPROVAL",
    "APPROVED",
    "EXECUTING",
    "EXECUTED",
    "REVIEWING",
    "FINALIZED",
    "SEALED",
    "HALT_CRITICAL",
    "BLOCKED",
    "ERROR",
    "CONTAMINATED",
)

TERMINAL = ("SEALED", "BLOCKED", "ERROR", "CONTAMINATED")

TRANSITIONS = {
    "NOT_STARTED": ("PLANNING", "BLOCKED"),
    "PLANNING": ("PLAN_READY", "BLOCKED", "ERROR"),
    "PLAN_READY": ("AWAITING_APPROVAL", "BLOCKED", "ERROR"),
    "AWAITING_APPROVAL": ("APPROVED", "BLOCKED", "ERROR"),
    "APPROVED": ("EXECUTING", "BLOCKED", "ERROR", "CONTAMINATED"),
    "EXECUTING": ("EXECUTED", "ERROR", "CONTAMINATED", "BLOCKED"),
    "EXECUTED": ("REVIEWING", "ERROR", "CONTAMINATED"),
    "REVIEWING": ("FINALIZED", "ERROR", "CONTAMINATED"),
    "FINALIZED": ("SEALED", "HALT_CRITICAL", "ERROR"),
    "SEALED": (),
    "HALT_CRITICAL": ("SEALED",),
    "BLOCKED": (),
    "ERROR": (),
    "CONTAMINATED": (),
}

# A plan-free audit — one answerable entirely with automatic read-only
# operations — still passes through PLAN_READY. It simply requires no
# approval, so AWAITING_APPROVAL to APPROVED is recorded as a no-op approval
# with an empty gated-operation list. There is no separate shortcut path,
# because a second path is a second thing to get wrong.

REPLICATED_PHASE_ORDER = ("RUN-A", "RUN-B", "COMPARISON")
SINGLE_PHASE_ORDER = ("RUN-A",)

KNOWN_PHASES = frozenset(REPLICATED_PHASE_ORDER)


class StateError(Exception):
    pass


def assert_state(value):
    if value not in STATES:
        raise StateError("unknown state: %r" % value)
    return value


def can_transition(current, target):
    assert_state(current)
    assert_state(target)
    return target in TRANSITIONS[current]


def transition(current, target):
    if not can_transition(current, target):
        raise StateError("invalid transition %s -> %s" % (current, target))
    return target


def is_terminal(state):
    assert_state(state)
    return state in TERMINAL


def phase_order(replications):
    if replications == 2:
        return REPLICATED_PHASE_ORDER
    if replications == 1:
        return SINGLE_PHASE_ORDER
    raise StateError("replications must be 1 or 2, got %r" % (replications,))


def assert_valid_completed_phases(replications, completed_phases):
    """Raise unless the completed phases are an exact ordered prefix.

    For a replicated audit exactly four situations exist:

        []                          → RUN-A is next
        [RUN-A]                     → RUN-B is next
        [RUN-A, RUN-B]              → COMPARISON is next
        [RUN-A, RUN-B, COMPARISON]  → the audit is complete

    Anything else is not a state this sequence can reach. The predecessor
    package walked the fixed order looking for the first phase that was not yet
    complete, which silently accepted `[RUN-B, COMPARISON]` — a comparison of
    one run against nothing, recorded as if RUN-A were merely pending. An
    impossible history that is accepted becomes an impossible history that is
    reported as fact.

    Rejected explicitly and by name: RUN-B without RUN-A, COMPARISON without
    RUN-A, COMPARISON without RUN-B, a repeated phase, phases out of order, and
    any name that is not a phase.
    """
    order = phase_order(replications)

    if completed_phases is None:
        raise StateError("completed phases must be a sequence, not None")
    if isinstance(completed_phases, (str, bytes)):
        raise StateError(
            "completed phases must be a sequence of phase names, not a string")

    completed = list(completed_phases)

    unknown = [p for p in completed if p not in KNOWN_PHASES]
    if unknown:
        raise StateError("unknown run phase in completed set: %r" % unknown)

    out_of_scope = [p for p in completed if p not in order]
    if out_of_scope:
        raise StateError(
            "phase %r cannot be complete for an audit with %d replication(s)"
            % (out_of_scope, replications))

    duplicates = sorted({p for p in completed if completed.count(p) > 1})
    if duplicates:
        raise StateError("phase completed more than once: %r" % duplicates)

    if len(completed) > len(order):
        raise StateError(
            "more completed phases than this audit has: %r" % completed)

    expected_prefix = list(order[:len(completed)])
    if completed != expected_prefix:
        missing = [p for p in expected_prefix if p not in completed]
        raise StateError(
            "completed phases %r are not the ordered prefix %r; the required "
            "order is %r and the missing prerequisite(s) are %r"
            % (completed, expected_prefix, list(order), missing))

    return completed


def next_run_phase(replications, completed_phases):
    """Return the next phase, or None when the audit is finished.

    For a replicated audit the order is fixed: RUN-A, RUN-B, COMPARISON.
    COMPARISON may not start before both runs are sealed, because a
    comparison of one run against nothing is not a comparison.
    """
    order = phase_order(replications)
    completed = assert_valid_completed_phases(replications, completed_phases)
    if len(completed) == len(order):
        return None
    return order[len(completed)]
