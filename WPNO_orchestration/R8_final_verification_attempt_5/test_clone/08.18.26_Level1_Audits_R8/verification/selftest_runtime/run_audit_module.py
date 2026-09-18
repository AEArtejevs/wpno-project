#!/usr/bin/env python3
"""Launcher for a frozen audit module, run as an isolated subprocess.

Why this file exists, and why it sits at the package root.

A plan step that needs a second implementation has to run one. The obvious
form, `python3 -I -B -m automation.<module>`, does not work: `-I` removes the
current directory from `sys.path`, so the interpreter cannot find `automation`
even when the controller's working directory is the package root. The obvious
repairs are all worse. Dropping `-I` gives the child the caller's environment
and user site directory. Putting the package root on PYTHONPATH does nothing
under `-I` and widens the environment allowlist otherwise. Running the module
file directly puts `automation/` on `sys.path` instead of the package root, so
its own relative imports fail.

A launcher at the package root solves it without giving anything up: under
`-I` the interpreter puts the *script's* directory first on `sys.path`, and
the script's directory is the package root.

There is no dynamic import here. `runpy.run_module` and
`importlib.import_module` would both take a module name and go and find it,
which is the same shape as the thing this package refuses everywhere else: a
name from a plan deciding what code runs. The three entry points are imported
statically, at the top of the file, and dispatched through a literal table. A
name that is not a key is not a module this launcher can reach — not because
a check rejected it, but because there is nothing to reach.
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from automation import a18_run_a_cli            # noqa: E402
from automation import a18_run_b_cli            # noqa: E402
from automation import a19_run_a_cli            # noqa: E402
from automation import a19_run_b_cli            # noqa: E402
from automation import independent_cms_cli      # noqa: E402
from automation import operation_catalog        # noqa: E402

ENTRY_POINTS = {
    "automation.a18_run_a_cli": a18_run_a_cli.main,
    "automation.a18_run_b_cli": a18_run_b_cli.main,
    "automation.a19_run_a_cli": a19_run_a_cli.main,
    "automation.a19_run_b_cli": a19_run_b_cli.main,
    "automation.independent_cms_cli": independent_cms_cli.main,
}


def main(argv):
    if len(argv) < 2:
        sys.stderr.write("usage: run_audit_module.py <module> [args...]\n")
        return 2
    module = argv[1]

    # The table and the catalogue must agree. If they ever drift, the drift is
    # reported here rather than resolved silently in favour of one of them.
    if set(ENTRY_POINTS) != set(operation_catalog.RUNNABLE_AUDIT_MODULES):
        sys.stderr.write(
            "the launcher's entry points %r and the catalogue's allowlist %r "
            "disagree\n" % (sorted(ENTRY_POINTS),
                            sorted(operation_catalog.RUNNABLE_AUDIT_MODULES)))
        return 2

    entry = ENTRY_POINTS.get(module)
    if entry is None:
        sys.stderr.write(
            "module %r is not one of this launcher's entry points %r\n"
            % (module, sorted(ENTRY_POINTS)))
        return 2

    return entry(list(argv[2:]))


if __name__ == "__main__":
    sys.exit(main(sys.argv))
