def _freeze_write(path, text):
    """Write one freeze artefact atomically and prove the bytes landed.

    Written to a temporary file beside the destination, flushed to the disk,
    and renamed into place. A reader therefore never sees a half-written
    artefact, and an interruption leaves either the previous file or the
    complete new one - never a truncated one that would hash to nothing
    anybody expects.
    """
    canonical = path_policy.assert_writable(path)
    path_policy.ensure_dir(os.path.dirname(canonical))
    temporary = canonical + ".freeze-tmp"
    with io.open(temporary, "w", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, canonical)
    written = hashing.sha256_file(canonical)
    expected = hashing.sha256_text(text)
    if written != expected:
        raise ControllerError(
            "FREEZE_ARTEFACT_WRITE_UNVERIFIED: %s wrote %s, expected %s"
            % (canonical, written, expected))
    return canonical, written
