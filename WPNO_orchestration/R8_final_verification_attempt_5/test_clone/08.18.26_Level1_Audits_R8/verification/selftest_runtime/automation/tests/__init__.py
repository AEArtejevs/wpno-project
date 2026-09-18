"""Controller self-tests.

These tests were NOT executed, collected or byte-compiled during the R3
package build. Codex verification runs them, and it runs them only inside an
isolated replica created below `verification/selftest_runtime/`, whose
`paths.json` declares roots that are themselves below `verification/`.

That topology is not a convenience. The verification prompt permits writes only
under `verification/`, while these tests must exercise the controller's real
work, state and evidence directories. Both requirements hold at once precisely
because the replica's LEVEL1_ROOT *is* a directory below `verification/`: the
tests write to `<replica>/work`, `<replica>/state` and `<replica>/evidence`
exactly as they would in production, and every one of those paths is inside the
permitted area. The predecessor package demanded both without saying how, which
is the contradiction recorded as VF-010.

The command, run from inside the replica and nowhere else:

    python3 -m unittest discover

No WPNO module is imported, no WPNO test is run, and no file outside the
replica's LEVEL1_ROOT is written.

Every test that needs scratch space uses LEVEL1_ROOT/work/_selftest and cleans
up after itself.
"""

import os
import sys

# Allow `python3 -m unittest discover` from LEVEL1_ROOT and from this
# directory alike, without requiring an installation step.
_HERE = os.path.dirname(os.path.abspath(__file__))
_LEVEL1_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _LEVEL1_ROOT not in sys.path:
    sys.path.insert(0, _LEVEL1_ROOT)

SELFTEST_DIRNAME = "_selftest"
