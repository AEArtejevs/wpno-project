"""Exclusive lock. One controller process at a time, always.

Two audit phases running concurrently would interleave state transitions and
evidence writes, and the resulting record would be unreadable. The lock is
mandatory and there is no option to skip it.
"""

import errno
import json
import os
import time

from . import path_policy


class LockError(Exception):
    pass


class ControllerLock(object):
    """A lock built on O_EXCL, which is atomic on every filesystem here.

    A stale lock is reported, never silently removed. Removing another
    process's lock is how two processes end up running at once.
    """

    def __init__(self, name="controller"):
        lock_dir = path_policy.ensure_dir(
            os.path.join(path_policy.LEVEL1_ROOT, "state"))
        self.path = path_policy.assert_writable(
            os.path.join(lock_dir, "%s.lock" % name))
        self.fd = None

    def acquire(self):
        payload = json.dumps({
            "pid": os.getpid(),
            "acquired": time.time(),
            "host_boot_safe": False,
        }).encode("utf-8")
        try:
            self.fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except OSError as exc:
            if exc.errno == errno.EEXIST:
                raise LockError(
                    "controller lock already held: %s. If no controller is "
                    "running, inspect and remove the file by hand — this code "
                    "will not remove another process's lock." % self.path)
            raise
        os.write(self.fd, payload)
        return self

    def release(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
        if os.path.exists(self.path):
            os.unlink(self.path)

    def __enter__(self):
        return self.acquire()

    def __exit__(self, exc_type, exc, tb):
        self.release()
        return False
