"""Perform the catalogued in-process operations.

IN_PROCESS means one thing in this package: this machine does it with the
standard library and no subprocess. Until this module existed the controller
had no implementation for that category. Its execute path appended the note
"in-process; performed by the worker" and continued to the next step. There
was no worker. Across the 43 frozen phases that silently skipped 165 of 307
planned steps, and twelve phases -- among them all four COMPARISON phases --
would have reported success having executed nothing at all.

R8. This module was built inside frozen R7, proven, and reverted out of it;
the incident is recorded in `lineage/R7_POST_FREEZE_INCIDENT`. It is reapplied
here, reviewed rather than copied, with three changes:

  * an unknown operation fails closed and by name
    (`UnsupportedInProcessOperation` -> UNSUPPORTED_IN_PROCESS_OPERATION)
    instead of raising a generic error that a caller might read as a
    measurement;
  * one operation writes. `MIME_EXTRACT_XML_PART_SANDBOX` decodes the
    intended XML part of a MIME entity into the writable work area, because
    L1-A33's accepted reference is a MIME multipart wrapper and must not be
    altered to suit the parser that reads it;
  * the sandbox switch assertion and the output-path confinement are
    expressed here rather than assumed of the caller.

The typed envelope around these handlers -- argument schema, path admission,
input and output hashing, expectation evaluation, evidence -- lives in
`in_process_executor`, which is the single entry point the live controller
and the rehearsal harness both call.

The rule this module exists to satisfy is the one in CLAUDE.md section 3:
proof is a task that ran. So every operation here really reads the bytes it
names, and every operation records what it found. Nothing returns a verdict.
These are measurement primitives; the audit's own criteria decide what the
measurement means.

Three properties hold for every operation below:

  * read-only, with exactly one declared exception.
    `MIME_EXTRACT_XML_PART_SANDBOX` writes its decoded part, and only below
    the writable work area, and never over its own source. Every other
    operation opens no path for writing at all. The exception is one
    operation rather than a general capability so that "which of these can
    write" is answered by a list and not by reading sixteen functions.
  * no subprocess, no socket, no import of any module under PROJECT_ROOT.
    A top-level import executes code; PYTHON_AST_PARSE parses instead.
  * bounded. Output is capped so a directory listing cannot become the
    evidence file.

Where a step carries an assertion parameter -- expected_sha256,
expect_contains, expect_absent -- the assertion is checked and a mismatch
fails the operation. A parameter that is accepted and ignored is worse than
one that is refused, because it reads as a check that happened.
"""

import ast
import csv
import email
import email.errors
import email.parser
import email.policy
import fnmatch
import hashlib
import io
import json
import os
import re
import stat
import tarfile
import unicodedata
import xml.etree.ElementTree as ElementTree
import zipfile

from . import path_policy

# A single operation's recorded result is capped here. The cap exists so a
# recursive listing of PROJECT_ROOT cannot turn into a multi-megabyte
# evidence file that nobody reads.
MAX_RESULT_ITEMS = 5000
MAX_READ_BYTES = 4 * 1024 * 1024

# Bounds for the one operation that decodes a container. The outer entity and
# the decoded part are bounded separately: a small envelope may declare a
# large part, and a bound on the file that arrived says nothing about the
# bytes that come out of it.
MAX_MIME_INPUT_BYTES = 8 * 1024 * 1024
MAX_MIME_PART_BYTES = 4 * 1024 * 1024

# The operations that write. Named, so the answer is a list.
WRITES_OUTPUT = frozenset(("MIME_EXTRACT_XML_PART_SANDBOX",))

UNSUPPORTED = "UNSUPPORTED_IN_PROCESS_OPERATION"


class InProcessError(Exception):
    """An in-process operation could not complete, or an assertion failed."""


class UnsupportedInProcessOperation(InProcessError):
    """The operation is classified IN_PROCESS and has no handler here.

    This is not a measurement and must never be recorded as one. A plan step
    naming an operation this module cannot perform is a defect in the plan or
    in the catalogue, and the run fails closed rather than continuing with a
    note -- which is precisely the shape of the defect R8 exists to repair.
    """


def _readable(path):
    """Resolve a path for reading under the package's path policy."""
    resolved = path_policy.assert_readable(path)
    path_policy.assert_no_symlink_escape(resolved)
    return resolved


def _writable_work_path(path, *, source):
    """Admit a destination for the one operation that writes.

    Three things are checked and none is assumed. The path is admitted by the
    package's write policy, which permits LEVEL1_ROOT and refuses everything
    else. It is then required to lie under `work/`, which is the mutable area
    the freeze deliberately does not cover -- writing a decoded part anywhere
    else would put a run-time artefact inside the control plane. Finally it
    is required not to be the source: an extraction that overwrote its own
    input would destroy the accepted reference it exists to preserve.

    The destination need not exist. Its parent directory is created, and a
    symlink anywhere in the destination is refused rather than followed,
    because following one is how a confined write lands outside its root.
    """
    canonical = path_policy.assert_writable(path)
    work_root = os.path.join(path_policy.LEVEL1_ROOT, "work")
    if not canonical.startswith(work_root + os.sep):
        raise InProcessError(
            "output must be written below work/: %s" % canonical)
    if canonical == source:
        raise InProcessError(
            "output would overwrite its own source: %s" % canonical)
    if os.path.lexists(canonical) and os.path.islink(canonical):
        raise InProcessError(
            "output destination is a symlink: %s" % canonical)
    parent = os.path.dirname(canonical)
    if os.path.lexists(parent):
        path_policy.assert_no_symlink_escape(parent)
    os.makedirs(parent, exist_ok=True)
    return canonical


def _require(params, name):
    if name not in params:
        raise InProcessError("parameter %r is required" % name)
    return params[name]


def _read_bytes(path, limit=MAX_READ_BYTES):
    with open(path, "rb") as handle:
        data = handle.read(limit + 1)
    truncated = len(data) > limit
    return (data[:limit], truncated)


def _decode(data):
    """Decode for text scanning, preserving byte identity when it is not UTF-8.

    latin-1 is the fallback on purpose: it is total and byte-preserving, so a
    literal byte sequence in a container file is still findable. The decoding
    actually used is recorded, because a caller reading match counts needs to
    know what was searched.
    """
    try:
        return (data.decode("utf-8"), "utf-8")
    except UnicodeDecodeError:
        return (data.decode("latin-1"), "latin-1")


def _sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


# ------------------------------------------------------------------ reading
def op_read_file_range(params):
    path = _readable(_require(params, "path"))
    start = int(params.get("start", 0))
    length = int(_require(params, "length"))
    if start < 0 or length < 0:
        raise InProcessError("start and length must not be negative")
    if length > MAX_READ_BYTES:
        raise InProcessError(
            "length %d exceeds MAX_READ_BYTES %d" % (length, MAX_READ_BYTES))
    size = os.path.getsize(path)
    with open(path, "rb") as handle:
        handle.seek(start)
        data = handle.read(length)
    text, encoding = _decode(data)
    return {
        "path": path,
        "file_size": size,
        "start": start,
        "requested_length": length,
        "returned_bytes": len(data),
        "reached_end_of_file": start + len(data) >= size,
        "sha256_of_range": hashlib.sha256(data).hexdigest(),
        "decoded_as": encoding,
        "text": text,
    }


def op_list_directory(params):
    root = _readable(_require(params, "path"))
    recursive = bool(params.get("recursive", False))
    contains = params.get("name_contains")
    if not os.path.isdir(root):
        raise InProcessError("not a directory: %s" % root)

    entries = []
    truncated = False
    if recursive:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames.sort()
            for name in sorted(dirnames) + sorted(filenames):
                full = os.path.join(dirpath, name)
                if contains is not None and contains not in name:
                    continue
                entries.append(os.path.relpath(full, root))
                if len(entries) > MAX_RESULT_ITEMS:
                    truncated = True
                    break
            if truncated:
                break
    else:
        for name in sorted(os.listdir(root)):
            if contains is not None and contains not in name:
                continue
            entries.append(name)
            if len(entries) > MAX_RESULT_ITEMS:
                truncated = True
                break

    return {
        "path": root,
        "recursive": recursive,
        "name_contains": contains,
        "match_count": len(entries[:MAX_RESULT_ITEMS]),
        "truncated": truncated,
        "entries": entries[:MAX_RESULT_ITEMS],
    }


def op_stat_file(params):
    """Measure a path. Absence is a result here, not an error.

    STAT_FILE exists to answer "what is at this path", and "nothing" is a
    real answer to that question -- it is what a negative control asking
    about a path that does not exist by construction is built to measure. So
    absence returns exit 0 with exists false, and only an unreadable or
    policy-refused path fails.

    CLAUDE.md section 5 draws the line this sits on: "not found" does not
    mean "does not exist". What is reported is therefore the measurement --
    this path did not resolve on this machine at this time -- and nothing
    broader than that.
    """
    path = _readable(_require(params, "path"))
    if not os.path.lexists(path):
        return {
            "path": path,
            "exists": False,
            "measured": "PATH_DID_NOT_RESOLVE_ON_THIS_MACHINE",
        }
    info = os.lstat(path)
    return {
        "path": path,
        "exists": True,
        "is_dir": stat.S_ISDIR(info.st_mode),
        "is_file": stat.S_ISREG(info.st_mode),
        "is_symlink": stat.S_ISLNK(info.st_mode),
        "size_bytes": info.st_size,
        "mode_octal": oct(stat.S_IMODE(info.st_mode)),
        "mtime_epoch": info.st_mtime,
        "nlink": info.st_nlink,
    }


def op_sha256_file(params):
    path = _readable(_require(params, "path"))
    digest = _sha256_file(path)
    result = {
        "path": path,
        "sha256": digest,
        "size_bytes": os.path.getsize(path),
    }
    expected = params.get("expected_sha256")
    if expected is not None:
        result["expected_sha256"] = expected
        result["matches_expected"] = (digest == expected)
        if digest != expected:
            raise InProcessError(
                "sha256 mismatch for %s: expected %s, measured %s"
                % (path, expected, digest))
    return result


# --------------------------------------------------------------- comparison
def op_compare_hashes(params):
    left = _readable(_require(params, "left"))
    right = _readable(_require(params, "right"))
    algorithms = params.get("algorithms") or ["sha256"]
    per_algorithm = {}
    for name in algorithms:
        try:
            left_digest = hashlib.new(name)
            right_digest = hashlib.new(name)
        except ValueError:
            raise InProcessError("unknown hash algorithm: %r" % name)
        for path, digest in ((left, left_digest), (right, right_digest)):
            with open(path, "rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
        per_algorithm[name] = {
            "left": left_digest.hexdigest(),
            "right": right_digest.hexdigest(),
            "equal": left_digest.hexdigest() == right_digest.hexdigest(),
        }

    result = {
        "left": left,
        "right": right,
        "algorithms": list(algorithms),
        "per_algorithm": per_algorithm,
        "equal": all(entry["equal"] for entry in per_algorithm.values()),
    }
    expected = params.get("expected_sha256")
    if expected is not None:
        measured = per_algorithm.get("sha256", {}).get("left")
        result["expected_sha256"] = expected
        result["left_matches_expected"] = (measured == expected)
        if measured != expected:
            raise InProcessError(
                "sha256 mismatch for %s: expected %s, measured %s"
                % (left, expected, measured))
    return result


def op_compare_binary_files(params):
    left = _readable(_require(params, "left"))
    right = _readable(_require(params, "right"))
    left_size = os.path.getsize(left)
    right_size = os.path.getsize(right)
    first_difference = None
    differing = 0
    with open(left, "rb") as lhs, open(right, "rb") as rhs:
        offset = 0
        while True:
            a = lhs.read(65536)
            b = rhs.read(65536)
            if not a and not b:
                break
            for index in range(max(len(a), len(b))):
                byte_a = a[index] if index < len(a) else None
                byte_b = b[index] if index < len(b) else None
                if byte_a != byte_b:
                    differing += 1
                    if first_difference is None:
                        first_difference = {
                            "offset": offset + index,
                            "left_byte": byte_a,
                            "right_byte": byte_b,
                        }
            offset += max(len(a), len(b))
            if not a or not b:
                break
    return {
        "left": left,
        "right": right,
        "left_size": left_size,
        "right_size": right_size,
        "sizes_equal": left_size == right_size,
        "identical": first_difference is None and left_size == right_size,
        "differing_byte_count": differing,
        "first_difference": first_difference,
        "left_sha256": _sha256_file(left),
        "right_sha256": _sha256_file(right),
    }


# ------------------------------------------------------------------ parsing
def op_python_ast_parse(params):
    """Parse Python source. Never import it -- a top-level import runs code."""
    path = _readable(_require(params, "path"))
    data, truncated = _read_bytes(path)
    if truncated:
        raise InProcessError("source exceeds MAX_READ_BYTES: %s" % path)
    source = data.decode("utf-8")
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as exc:
        raise InProcessError("syntax error in %s: %s" % (path, exc))

    imports = []
    functions = []
    classes = []
    calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(node.name)
        elif isinstance(node, ast.ClassDef):
            classes.append(node.name)
        elif isinstance(node, ast.Call):
            target = node.func
            if isinstance(target, ast.Name):
                calls.append(target.id)
            elif isinstance(target, ast.Attribute):
                calls.append(target.attr)
    return {
        "path": path,
        "parsed": True,
        "imported_module_was_executed": False,
        "sha256": hashlib.sha256(data).hexdigest(),
        "source_bytes": len(data),
        "imports": sorted(set(imports))[:MAX_RESULT_ITEMS],
        "functions": sorted(set(functions))[:MAX_RESULT_ITEMS],
        "classes": sorted(set(classes))[:MAX_RESULT_ITEMS],
        "called_names": sorted(set(calls))[:MAX_RESULT_ITEMS],
    }


def op_parse_json_readonly(params):
    path = _readable(_require(params, "path"))
    data, truncated = _read_bytes(path)
    if truncated:
        raise InProcessError("file exceeds MAX_READ_BYTES: %s" % path)
    text, encoding = _decode(data)
    try:
        parsed = json.loads(text)
    except ValueError as exc:
        raise InProcessError("not valid JSON: %s: %s" % (path, exc))

    if isinstance(parsed, dict):
        shape, size = "object", len(parsed)
        keys = sorted(parsed.keys())[:MAX_RESULT_ITEMS]
    elif isinstance(parsed, list):
        shape, size, keys = "array", len(parsed), []
    else:
        shape, size, keys = type(parsed).__name__, None, []

    result = {
        "path": path,
        "parsed": True,
        "decoded_as": encoding,
        "sha256": hashlib.sha256(data).hexdigest(),
        "shape": shape,
        "size": size,
        "top_level_keys": keys,
    }

    # The assertions are checked against the raw document text, so a value
    # nested anywhere is still seen. An assertion that is accepted and not
    # checked would read as a check that happened.
    contains = params.get("expect_contains")
    if contains is not None:
        result["expect_contains"] = contains
        result["expect_contains_found"] = contains in text
        if contains not in text:
            raise InProcessError(
                "expect_contains %r not found in %s" % (contains, path))
    absent = params.get("expect_absent")
    if absent is not None:
        result["expect_absent"] = absent
        result["expect_absent_found"] = absent in text
        if absent in text:
            raise InProcessError(
                "expect_absent %r was found in %s" % (absent, path))
    return result


def op_parse_csv_readonly(params):
    path = _readable(_require(params, "path"))
    data, truncated = _read_bytes(path)
    text, encoding = _decode(data)
    reader = csv.reader(io.StringIO(text))
    rows = []
    for row in reader:
        rows.append(row)
        if len(rows) > MAX_RESULT_ITEMS:
            truncated = True
            break
    header = rows[0] if rows else []
    return {
        "path": path,
        "parsed": True,
        "decoded_as": encoding,
        "sha256": hashlib.sha256(data).hexdigest(),
        "row_count": len(rows[:MAX_RESULT_ITEMS]),
        "column_count": len(header),
        "header": header,
        "truncated": truncated,
        "rows": rows[:MAX_RESULT_ITEMS],
    }


def op_count_text_matches(params):
    """Count pattern matches, honouring the word-boundary flag.

    The flag is not decoration. CLAUDE.md section 10 records what its absence
    cost here already: a pattern for `bea` matched `Projektbeauftragung`,
    `Beanstandung` and `Bearbeitung` -- twelve hits, none of them real. When
    word_boundary is true every pattern is wrapped in \\b on both sides.
    """
    patterns = _require(params, "patterns")
    if not isinstance(patterns, list) or not patterns:
        raise InProcessError("patterns must be a non-empty list")
    word_boundary = bool(params.get("word_boundary", False))
    normal_form = params.get("normal_form")
    if normal_form is not None and normal_form not in ("NFC", "NFD", "NFKC", "NFKD"):
        raise InProcessError("unsupported normal_form: %r" % normal_form)

    targets = []
    if "path" in params:
        targets.append(_readable(params["path"]))
    if "root" in params:
        root = _readable(params["root"])
        globs = params.get("include_globs") or ["*"]
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames.sort()
            for name in sorted(filenames):
                if any(fnmatch.fnmatch(name, pattern) for pattern in globs):
                    targets.append(os.path.join(dirpath, name))
            if len(targets) > MAX_RESULT_ITEMS:
                break
    if not targets:
        raise InProcessError("neither path nor root produced a file to scan")

    compiled = []
    for pattern in patterns:
        expression = r"\b%s\b" % pattern if word_boundary else pattern
        try:
            compiled.append((pattern, re.compile(expression)))
        except re.error as exc:
            raise InProcessError("bad pattern %r: %s" % (pattern, exc))

    per_pattern = {pattern: 0 for pattern in patterns}
    per_file = {}
    files_scanned = 0
    files_unreadable = []
    for target in targets[:MAX_RESULT_ITEMS]:
        try:
            data, _ = _read_bytes(target)
        except (OSError, path_policy.PathPolicyError):
            files_unreadable.append(target)
            continue
        text, _ = _decode(data)
        if normal_form:
            text = unicodedata.normalize(normal_form, text)
        files_scanned += 1
        hits = {}
        for pattern, expression in compiled:
            count = len(expression.findall(text))
            if count:
                hits[pattern] = count
                per_pattern[pattern] += count
        if hits:
            per_file[target] = hits

    return {
        "patterns": list(patterns),
        "word_boundary": word_boundary,
        "normal_form": normal_form,
        "files_scanned": files_scanned,
        "files_unreadable": files_unreadable[:MAX_RESULT_ITEMS],
        "total_matches": sum(per_pattern.values()),
        "matches_per_pattern": per_pattern,
        "matches_per_file": dict(list(per_file.items())[:MAX_RESULT_ITEMS]),
    }


# --------------------------------------------------------------- containers
def op_zip_list(params):
    path = _readable(_require(params, "path"))
    if not zipfile.is_zipfile(path):
        raise InProcessError("not a zip archive: %s" % path)
    entries = []
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist()[:MAX_RESULT_ITEMS]:
            entries.append({
                "name": info.filename,
                "size": info.file_size,
                "compressed_size": info.compress_size,
                "crc32": "%08x" % (info.CRC & 0xFFFFFFFF),
                "is_dir": info.is_dir(),
                "date_time": list(info.date_time),
            })
    return {
        "path": path,
        "archive_sha256": _sha256_file(path),
        "entry_count": len(entries),
        "entries": entries,
    }


def op_tar_list(params):
    path = _readable(_require(params, "path"))
    if not tarfile.is_tarfile(path):
        raise InProcessError("not a tar archive: %s" % path)
    entries = []
    with tarfile.open(path, "r:*") as archive:
        for member in archive:
            entries.append({
                "name": member.name,
                "size": member.size,
                "is_file": member.isfile(),
                "is_dir": member.isdir(),
                "is_symlink": member.issym() or member.islnk(),
                "link_target": member.linkname or None,
                "mode_octal": oct(member.mode),
            })
            if len(entries) >= MAX_RESULT_ITEMS:
                break
    return {
        "path": path,
        "archive_sha256": _sha256_file(path),
        "entry_count": len(entries),
        "entries": entries,
    }


# ---------------------------------------------------------------------- XML
def _assert_xml_sandbox(params, text, label):
    """Enforce the sandbox switches the plan asked for, rather than trusting them.

    A plan that says resolve_entities false and is handed a document carrying
    entity declarations must not quietly parse it anyway. XXE is the whole
    reason these switches are in the plan.
    """
    if params.get("no_network") is not True:
        raise InProcessError("%s requires no_network true" % label)
    if params.get("resolve_entities") is not False:
        raise InProcessError("%s requires resolve_entities false" % label)
    if params.get("load_dtd") is not False:
        raise InProcessError("%s requires load_dtd false" % label)
    if params.get("xinclude") not in (None, False):
        raise InProcessError("%s requires xinclude false or absent" % label)

    head = text[:65536]
    findings = {
        "doctype_present": bool(re.search(r"<!DOCTYPE", head, re.IGNORECASE)),
        "entity_declaration_present": bool(
            re.search(r"<!ENTITY", head, re.IGNORECASE)),
        "external_reference_present": bool(
            re.search(r"SYSTEM\s+[\"']|PUBLIC\s+[\"']", head)),
    }
    if findings["entity_declaration_present"]:
        raise InProcessError(
            "%s refused: the document declares entities and "
            "resolve_entities is false" % label)
    if findings["external_reference_present"]:
        raise InProcessError(
            "%s refused: the document references an external identifier and "
            "no_network is true" % label)
    return findings


def _parse_xml_text(text, label):
    # ElementTree's parser resolves no external entities and fetches nothing.
    try:
        return ElementTree.fromstring(text)
    except ElementTree.ParseError as exc:
        raise InProcessError("%s: XML parse error: %s" % (label, exc))


def _element_summary(root):
    tags = {}
    total = 0
    for element in root.iter():
        total += 1
        tags[element.tag] = tags.get(element.tag, 0) + 1
    top = sorted(tags.items(), key=lambda item: (-item[1], item[0]))
    return {
        "root_tag": root.tag,
        "element_count": total,
        "distinct_tags": len(tags),
        "most_common_tags": top[:50],
    }


def op_xml_parse_sandbox(params):
    path = _readable(_require(params, "path"))
    data, truncated = _read_bytes(path)
    if truncated:
        raise InProcessError("file exceeds MAX_READ_BYTES: %s" % path)
    text, encoding = _decode(data)
    sandbox = _assert_xml_sandbox(params, text, "XML_PARSE_SANDBOX")
    root = _parse_xml_text(text, "XML_PARSE_SANDBOX")
    result = {
        "path": path,
        "parsed": True,
        "decoded_as": encoding,
        "sha256": hashlib.sha256(data).hexdigest(),
        "sandbox": {
            "no_network": True,
            "resolve_entities": False,
            "load_dtd": False,
            "xinclude": False,
        },
        "document_findings": sandbox,
    }
    result.update(_element_summary(root))
    return result


def op_docx_parse_sandbox(params):
    path = _readable(_require(params, "path"))
    if not zipfile.is_zipfile(path):
        raise InProcessError("not a docx (not a zip container): %s" % path)
    select = params.get("select")
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if "word/document.xml" not in names:
            raise InProcessError("no word/document.xml in %s" % path)
        raw = archive.read("word/document.xml")
    text, encoding = _decode(raw)
    sandbox = _assert_xml_sandbox(params, text, "DOCX_PARSE_SANDBOX")
    root = _parse_xml_text(text, "DOCX_PARSE_SANDBOX")

    word = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    paragraphs = 0
    for _ in root.iter(word + "p"):
        paragraphs += 1
    instructions = [
        (element.text or "")
        for element in root.iter(word + "instrText")
    ]

    result = {
        "path": path,
        "parsed": True,
        "decoded_as": encoding,
        "docx_sha256": _sha256_file(path),
        "document_xml_sha256": hashlib.sha256(raw).hexdigest(),
        "zip_entry_count": len(names),
        "paragraph_count": paragraphs,
        "field_instruction_count": len(instructions),
        "sandbox": {
            "no_network": True,
            "resolve_entities": False,
            "load_dtd": False,
        },
        "document_findings": sandbox,
    }
    result.update(_element_summary(root))

    if select == "toc":
        toc = [value for value in instructions if "TOC" in value.upper()]
        result["select"] = "toc"
        result["toc_field_count"] = len(toc)
        result["toc_field_instructions"] = toc[:MAX_RESULT_ITEMS]
        result["has_toc_field"] = bool(toc)
    elif select is not None:
        raise InProcessError("unsupported select: %r" % select)
    return result


# ------------------------------------------------------------------ imports
def op_docker_metadata_import(params):
    """Read container metadata from an export. Never contact the daemon."""
    export = _readable(_require(params, "export"))
    if params.get("no_socket") is not True:
        raise InProcessError(
            "DOCKER_METADATA_IMPORT requires no_socket true; this operation "
            "reads an exported file and never contacts the docker daemon")
    data, truncated = _read_bytes(export)
    if truncated:
        raise InProcessError("export exceeds MAX_READ_BYTES: %s" % export)
    text, encoding = _decode(data)

    # A docker export is JSON when it came from `--format {{json .}}` and
    # tabular text when it came from a plain `docker ps` or `image history`.
    # Both are exports and both are legitimate here; what must never happen
    # is contacting the daemon. So the format is detected and recorded rather
    # than demanded, and the record count is derived from whichever it is.
    result = {
        "export": export,
        "socket_used": False,
        "daemon_contacted": False,
        "decoded_as": encoding,
        "sha256": hashlib.sha256(data).hexdigest(),
    }
    try:
        parsed = json.loads(text)
    except ValueError:
        lines = [line for line in text.splitlines() if line.strip()]
        result.update({
            "export_format": "TABULAR_TEXT",
            "shape": "text",
            "line_count": len(lines),
            "record_count": max(len(lines) - 1, 0),
            "header_line": lines[0][:2000] if lines else None,
            "top_level_keys": [],
        })
        return result

    result.update({
        "export_format": "JSON",
        "shape": type(parsed).__name__,
        "record_count": (len(parsed)
                         if isinstance(parsed, (list, dict)) else None),
        "top_level_keys": (sorted(parsed.keys())[:MAX_RESULT_ITEMS]
                           if isinstance(parsed, dict) else []),
    })
    return result


def op_database_evidence_import(params):
    """Read database evidence from an export. Never open a connection."""
    export = _readable(_require(params, "export"))
    if params.get("no_connection") is not True:
        raise InProcessError(
            "DATABASE_EVIDENCE_IMPORT requires no_connection true; this "
            "operation reads an exported file and never connects to a server")
    data, truncated = _read_bytes(export)
    if truncated:
        raise InProcessError("export exceeds MAX_READ_BYTES: %s" % export)

    digest = hashlib.sha256(data).hexdigest()
    if data[:16] == b"SQLite format 3\x00":
        raise InProcessError(
            "export is a live SQLite database file, not an export; this "
            "operation does not open database files")
    text, encoding = _decode(data)
    try:
        parsed = json.loads(text)
    except ValueError as exc:
        raise InProcessError("export is not valid JSON: %s: %s" % (export, exc))
    return {
        "export": export,
        "connection_opened": False,
        "server_contacted": False,
        "decoded_as": encoding,
        "sha256": digest,
        "shape": type(parsed).__name__,
        "record_count": len(parsed) if isinstance(parsed, (list, dict)) else None,
        "top_level_keys": (sorted(parsed.keys())[:MAX_RESULT_ITEMS]
                           if isinstance(parsed, dict) else []),
    }



# --------------------------------------------------------------------- MIME
#
# Why this operation exists (R8, L1-A33).
#
# `references/REF-11-563203462.xml` is named .xml and is not XML. Its first
# bytes are `MIME-Version: 1.0` and its Content-Type is Multipart/Related; the
# XML lives in a part inside it. The frozen R7 plan applied XML_PARSE_SANDBOX
# to it directly and the parser refused at line 1 column 0 -- correctly. The
# operation had been chosen from the file extension, which CLAUDE.md section 4
# rules out: a filename is not evidence of content.
#
# The reference is accepted material and is not altered. The intended part is
# decoded into the writable work area and the XML parser is pointed at that.
#
# One measured detail decides the parser policy, and it is the reason this
# does not use `email.policy.default`. The entity's boundary parameter is
# unquoted and contains `/`, which RFC 2045 lists as a tspecial:
#
#     boundary=MIME_boundary_fw73kdtYTcsDb2DHUIDsf/KG00+cqYQn
#
# `email.policy.default` stops at the `/`, takes the boundary to be
# `MIME_boundary_fw73kdtYTcsDb2DHUIDsf`, finds no part matching it, and
# returns a message that reports `is_multipart()` false with zero parts. It
# does not raise. `compat32` reads the boundary whole and finds the part.
#
# Measured on this file: default -> 0 parts, defects
# [StartBoundaryNotFoundDefect, MultipartInvariantViolationDefect];
# compat32 -> 1 part, text/xml, Content-ID <osci@message>, 15905 bytes,
# no defects. A parser that silently finds nothing and reports success is the
# exact failure mode CLAUDE.md section 10 collects, so the policy is compat32
# and the defect list is checked rather than ignored.


def op_mime_extract_xml_part_sandbox(params):
    """Decode the intended XML part of a MIME entity into work/.

    Nothing is executed, nothing is fetched and no entity is resolved: the
    part is bytes, and it is written as bytes. Selection is deterministic or
    it is refused -- two candidate parts with nothing to choose between them
    is an ambiguity the plan has to settle, not one this operation may settle
    for it.
    """
    source = _readable(_require(params, "path"))
    if params.get("no_network") is not True:
        raise InProcessError(
            "MIME_EXTRACT_XML_PART_SANDBOX requires no_network true")
    if params.get("resolve_entities") is not False:
        raise InProcessError(
            "MIME_EXTRACT_XML_PART_SANDBOX requires resolve_entities false")

    destination = _writable_work_path(_require(params, "out"), source=source)
    wanted_type = params.get("select_content_type", "text/xml")
    wanted_id = params.get("select_content_id")

    size = os.path.getsize(source)
    if size > MAX_MIME_INPUT_BYTES:
        raise InProcessError(
            "MIME entity is %d bytes, over the %d byte bound: %s"
            % (size, MAX_MIME_INPUT_BYTES, source))
    with open(source, "rb") as handle:
        raw = handle.read(MAX_MIME_INPUT_BYTES + 1)
    if len(raw) > MAX_MIME_INPUT_BYTES:
        raise InProcessError("MIME entity exceeds the input bound: %s" % source)
    outer_sha256 = hashlib.sha256(raw).hexdigest()

    parser = email.parser.BytesParser(policy=email.policy.compat32)
    try:
        message = parser.parsebytes(raw)
    except (email.errors.MessageError, ValueError) as exc:
        raise InProcessError("malformed MIME entity: %s: %s" % (source, exc))

    defects = ["%s" % type(d).__name__ for d in message.defects]
    for part in message.walk():
        defects.extend("%s" % type(d).__name__ for d in part.defects)
    if defects:
        raise InProcessError(
            "malformed MIME entity: %s: defects %s" % (source, sorted(defects)))
    if not message.is_multipart():
        raise InProcessError(
            "not a multipart MIME entity: %s is %s"
            % (source, message.get_content_type()))

    candidates = []
    for index, part in enumerate(message.walk()):
        if part.is_multipart():
            continue
        headers = {
            "Content-Type": part.get("Content-Type"),
            "Content-ID": part.get("Content-ID"),
            "Content-Transfer-Encoding": part.get("Content-Transfer-Encoding"),
            "Content-Disposition": part.get("Content-Disposition"),
        }
        if part.get_content_type() != wanted_type:
            continue
        if wanted_id is not None and (part.get("Content-ID") or "") != wanted_id:
            continue
        candidates.append((index, part, headers))

    if not candidates:
        raise InProcessError(
            "no %s part in %s%s" % (wanted_type, source,
                                    "" if wanted_id is None
                                    else " with Content-ID %s" % wanted_id))
    if len(candidates) > 1:
        raise InProcessError(
            "%d candidate %s parts in %s and the plan names no Content-ID to "
            "choose between them; an ambiguous selection is refused"
            % (len(candidates), wanted_type, source))

    index, part, headers = candidates[0]
    decoded = part.get_payload(decode=True)
    if decoded is None:
        raise InProcessError("selected MIME part has no decodable payload")
    if len(decoded) > MAX_MIME_PART_BYTES:
        raise InProcessError(
            "decoded part is %d bytes, over the %d byte bound"
            % (len(decoded), MAX_MIME_PART_BYTES))

    with open(destination, "wb") as handle:
        handle.write(decoded)
        handle.flush()
        os.fsync(handle.fileno())

    written = _sha256_file(destination)
    if written != hashlib.sha256(decoded).hexdigest():
        raise InProcessError("written part does not match the decoded bytes")
    if _sha256_file(source) != outer_sha256:
        raise InProcessError("source changed during extraction: %s" % source)

    return {
        "path": source,
        "out": destination,
        "source_sha256": outer_sha256,
        "source_bytes": size,
        "source_unchanged": True,
        "mime_parser_policy": "compat32",
        "mime_parser_policy_reason": (
            "the entity's boundary is unquoted and contains '/', a tspecial; "
            "email.policy.default truncates it there, finds no part and "
            "reports success with zero parts"),
        "mime_defects": [],
        "outer_content_type": message.get_content_type(),
        "boundary": message.get_boundary(),
        "part_count": sum(1 for p in message.walk() if not p.is_multipart()),
        "selected_part_index": index,
        "selected_by": {"content_type": wanted_type,
                        "content_id": wanted_id},
        "selection_headers": headers,
        "candidate_part_count": 1,
        "extracted_bytes": len(decoded),
        "extracted_sha256": written,
        "network_used": False,
        "entities_resolved": False,
        "content_executed": False,
    }



# ------------------------------------------------------------------ novelty
#
# Why this operation exists (R8, L1-A16).
#
# `prove_cases_are_novel` bound COMPARE_HASHES to two directories:
#
#     left  = work/L1-A16/RUN-A/cases
#     right = /home/ubuntu/project/WPNO/ap18
#
# COMPARE_HASHES opens files, so a directory raised IsADirectoryError and the
# step could never run. It never had run: R7 deferred it because its input was
# absent, and the deferral hid the defect for two revisions.
#
# The type error is the smaller half. Even had it worked, the digest of one
# directory against the digest of another answers nothing about whether case
# N3 repeats W2 -- novelty is a per-case question, and an aggregate comparison
# collapses five answers into one bit. And `ap18` is the AP18 source tree; the
# specification names `ap18/korpus_docx` as the corpus, seven files, W1 to W5
# plus two clean ones.
#
# So this measures what the specification asks for: every candidate hashed,
# every corpus member hashed, and each candidate reported unique or duplicate
# against the corpus by content. Names are not consulted, so a duplicate under
# a new filename is still a duplicate -- which is exactly the evasion a
# name-based check would miss.
#
# It fails closed. A corpus that is absent, empty, or of a size the plan did
# not expect is refused, because "no duplicates found" and "nothing to compare
# against" are the same answer to a caller that only reads the verdict, and
# they are not the same fact.


def op_prove_set_novelty(params):
    """Prove each candidate is absent from a reference corpus, by content."""
    candidate_root = _readable(_require(params, "candidate_root"))
    reference_root = _readable(_require(params, "reference_root"))
    reference_set_id = _require(params, "reference_set_id")
    globs = params.get("include_globs") or ["*"]
    expected_entries = params.get("expected_reference_entry_count")
    require_non_empty = params.get("require_non_empty_reference", True)

    for label, root in (("candidate_root", candidate_root),
                        ("reference_root", reference_root)):
        if not os.path.isdir(root):
            raise InProcessError(
                "%s is not a directory: %s" % (label, root))

    def inventory(root):
        """A deterministic, sorted, non-recursive inventory with digests."""
        rows = []
        for name in sorted(os.listdir(root)):
            full = os.path.join(root, name)
            if os.path.islink(full):
                raise InProcessError(
                    "inventory refuses a symlink: %s" % full)
            if not os.path.isfile(full):
                continue
            if not any(fnmatch.fnmatch(name, pattern) for pattern in globs):
                continue
            rows.append({"name": name,
                         "path": full,
                         "sha256": _sha256_file(full),
                         "size": os.path.getsize(full)})
            if len(rows) > MAX_RESULT_ITEMS:
                raise InProcessError(
                    "inventory of %s exceeds %d entries"
                    % (root, MAX_RESULT_ITEMS))
        return rows

    reference = inventory(reference_root)
    if require_non_empty and not reference:
        raise InProcessError(
            "the reference corpus %s is empty; novelty cannot be proven "
            "against nothing, and an empty corpus would make every candidate "
            "look novel" % reference_root)
    if expected_entries is not None and len(reference) != expected_entries:
        raise InProcessError(
            "the reference corpus %s holds %d entries and the plan expects "
            "%d; the corpus this audit was written against is not the corpus "
            "on disk" % (reference_root, len(reference), expected_entries))

    candidates = inventory(candidate_root)
    if not candidates:
        raise InProcessError(
            "no candidate matched %r under %s" % (globs, candidate_root))

    # The digest of the corpus's digest set. It identifies the corpus a run
    # was measured against, independently of file order or of any one name.
    joined = "\n".join(sorted(row["sha256"] for row in reference)) + "\n"
    reference_hash_set_sha256 = hashlib.sha256(
        joined.encode("utf-8")).hexdigest()

    by_digest = {}
    for row in reference:
        by_digest.setdefault(row["sha256"], []).append(row["name"])

    cases = []
    for row in candidates:
        matches = by_digest.get(row["sha256"], [])
        cases.append({
            "CASE_ID": os.path.splitext(row["name"])[0],
            "CASE_PATH": row["path"],
            "CASE_SHA256": row["sha256"],
            "CASE_SIZE": row["size"],
            "DUPLICATE_MATCHES": sorted(matches),
            "UNIQUE_RESULT": not matches,
            "MEASURED_REASON": (
                "no reference entry has this content digest"
                if not matches else
                "byte-identical to reference entr%s %s; a different filename "
                "does not make it a different document"
                % ("y" if len(matches) == 1 else "ies", ", ".join(sorted(matches)))),
        })

    duplicates = [c for c in cases if not c["UNIQUE_RESULT"]]
    return {
        "candidate_root": candidate_root,
        "REFERENCE_SET_ID": reference_set_id,
        "reference_root": reference_root,
        "REFERENCE_ENTRY_COUNT": len(reference),
        "REFERENCE_HASH_SET_SHA256": reference_hash_set_sha256,
        "reference_entries": [{"name": r["name"], "sha256": r["sha256"]}
                              for r in reference],
        "include_globs": list(globs),
        "candidate_count": len(cases),
        "cases": cases,
        "duplicate_count": len(duplicates),
        "unique_count": len(cases) - len(duplicates),
        "all_novel": not duplicates,
        "comparison_basis": "content digest only; filenames are not consulted",
        "MEASURED_REASON": (
            "all %d candidates are absent from the %d-entry reference corpus"
            % (len(cases), len(reference)) if not duplicates else
            "%d of %d candidates repeat a reference entry: %s"
            % (len(duplicates), len(cases),
               ", ".join("%s=%s" % (c["CASE_ID"], ",".join(c["DUPLICATE_MATCHES"]))
                         for c in duplicates))),
    }


HANDLERS = {
    "READ_FILE_RANGE": op_read_file_range,
    "LIST_DIRECTORY": op_list_directory,
    "STAT_FILE": op_stat_file,
    "SHA256_FILE": op_sha256_file,
    "COMPARE_HASHES": op_compare_hashes,
    "COMPARE_BINARY_FILES": op_compare_binary_files,
    "PYTHON_AST_PARSE": op_python_ast_parse,
    "PARSE_JSON_READONLY": op_parse_json_readonly,
    "PARSE_CSV_READONLY": op_parse_csv_readonly,
    "COUNT_TEXT_MATCHES": op_count_text_matches,
    "ZIP_LIST": op_zip_list,
    "TAR_LIST": op_tar_list,
    "XML_PARSE_SANDBOX": op_xml_parse_sandbox,
    "DOCX_PARSE_SANDBOX": op_docx_parse_sandbox,
    "DOCKER_METADATA_IMPORT": op_docker_metadata_import,
    "DATABASE_EVIDENCE_IMPORT": op_database_evidence_import,
    "MIME_EXTRACT_XML_PART_SANDBOX": op_mime_extract_xml_part_sandbox,
    "PROVE_SET_NOVELTY": op_prove_set_novelty,
}


def supported(operation):
    """True when this module can actually perform the operation."""
    return operation in HANDLERS


def unsupported(operations):
    """The operations in `operations` that have no handler here.

    Used by plan assembly and by the executor's own self-check, so that a
    plan binding an operation nothing can perform is refused at build time
    rather than discovered under an approved token.
    """
    return sorted(name for name in operations if name not in HANDLERS)


def perform(operation, params):
    """Perform one in-process operation.

    Returns (exit_code, result). exit_code is 0 when the operation completed
    and every assertion it carried held, and 1 when it did not. The caller
    records both outcomes as evidence; a failed assertion is a measurement,
    not a crash.
    """
    handler = HANDLERS.get(operation)
    if handler is None:
        raise UnsupportedInProcessOperation(
            "%s: %s is classified IN_PROCESS and has no handler in this "
            "module" % (UNSUPPORTED, operation))
    try:
        return (0, handler(dict(params or {})))
    except InProcessError as exc:
        return (1, {"operation": operation, "failed": True, "reason": str(exc)})
    except (OSError, ValueError, KeyError, TypeError,
            path_policy.PathPolicyError) as exc:
        return (1, {"operation": operation, "failed": True,
                    "reason": "%s: %s" % (type(exc).__name__, exc)})
