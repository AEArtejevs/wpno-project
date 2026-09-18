"""Perform the catalogued in-process operations.

IN_PROCESS means one thing in this package: this machine does it with the
standard library and no subprocess. Until this module existed the controller
had no implementation for that category. Its execute path appended the note
"in-process; performed by the worker" and continued to the next step. There
was no worker. Across the 43 frozen phases that silently skipped 165 of 307
planned steps, and twelve phases -- among them all four COMPARISON phases --
would have reported success having executed nothing at all.

The rule this module exists to satisfy is the one in CLAUDE.md section 3:
proof is a task that ran. So every operation here really reads the bytes it
names, and every operation records what it found. Nothing returns a verdict.
These are measurement primitives; the audit's own criteria decide what the
measurement means.

Three properties hold for every operation below:

  * read-only. No path is ever opened for writing.
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


class InProcessError(Exception):
    """An in-process operation could not complete, or an assertion failed."""


def _readable(path):
    """Resolve a path for reading under the package's path policy."""
    resolved = path_policy.assert_readable(path)
    path_policy.assert_no_symlink_escape(resolved)
    return resolved


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
}


def perform(operation, params):
    """Perform one in-process operation.

    Returns (exit_code, result). exit_code is 0 when the operation completed
    and every assertion it carried held, and 1 when it did not. The caller
    records both outcomes as evidence; a failed assertion is a measurement,
    not a crash.
    """
    handler = HANDLERS.get(operation)
    if handler is None:
        raise InProcessError(
            "%s is classified IN_PROCESS but has no implementation" % operation)
    try:
        return (0, handler(dict(params or {})))
    except InProcessError as exc:
        return (1, {"operation": operation, "failed": True, "reason": str(exc)})
    except (OSError, ValueError, KeyError, TypeError,
            path_policy.PathPolicyError) as exc:
        return (1, {"operation": operation, "failed": True,
                    "reason": "%s: %s" % (type(exc).__name__, exc)})
