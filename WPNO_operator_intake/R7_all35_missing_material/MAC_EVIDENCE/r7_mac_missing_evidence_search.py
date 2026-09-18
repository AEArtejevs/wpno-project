#!/usr/bin/env python3
import csv
import hashlib
import json
import os
import plistlib
import re
import shutil
import stat
import subprocess
import sys
import textwrap
import time
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

MAC_HOME = Path("/Users/martinotten")
WPNO_ROOT = MAC_HOME / "WPNO"
OUTPUT_ROOT = MAC_HOME / "Downloads/2026-08-27_R7_Mac_Missing_Evidence_Search"

TARGET_ROOTS = [
    WPNO_ROOT,
    MAC_HOME / "Desktop",
    MAC_HOME / "Documents",
    MAC_HOME / "Downloads",
    MAC_HOME / "Library/CloudStorage",
    MAC_HOME / "Library/Mobile Documents/com~apple~CloudDocs",
    MAC_HOME / ".claude",
    MAC_HOME / ".codex",
]

EXTRA_FILES = [
    MAC_HOME / ".zsh_history",
]
EXTRA_DIRS = [
    MAC_HOME / "Library/Application Support/Claude",
]

PRUNE_NAMES = {
    ".git",
    "node_modules",
    "venv",
    ".venv",
    "__pycache__",
    "site-packages",
    "Caches",
    ".Trash",
    "Trash",
    "DerivedData",
    "build",
    "dist",
}

AUDIT_REPEAT_RE = re.compile(r"referent of 376 is undefined", re.I)
HEX64_RE = re.compile(r"\b[a-fA-F0-9]{64}\b")
SECRET_FIELD_RE = re.compile(r"(?i)(api[_-]?key|token|secret|password|passwd|credential|authorization|bearer|private[_-]?key)")

REF06_PRIORITIES = re.compile(
    r"(Schriftsatz|BGH|Zitat|citation|43|110|real|final|master|register|L1-A14|A14)",
    re.I,
)
BGH_CITE_RE = re.compile(
    r"\b(?:BGH|BGHZ|BGHR|NJW|NStZ|MDR|ZIP|GRUR|WM|VersR|FamRZ|BeckRS)\b[^.\n]{0,120}?(?:\d{1,3},\s?\d{1,4}|\d{4},\s?\d{1,5}|[IVX]{1,5}\s?[A-Z]{1,4}\s?\d+/\d{2})",
    re.I,
)

REF12_TERMS = [
    "376", '"376"', "376 hash", "376 file", "376 artefact", "376 artifact",
    "376 record", "376 items", "376 entries", "Independent 376 hash remeasurement",
    "REF-12", "L1-A29",
]
REF05_TERMS = [
    "BGH_REGISTER", "validity period", "Gültigkeitszeitraum", "Stand:",
    "as of", "Stichtag", "Geschäftsverteilungsplan", "Präsidiumsbeschlüsse",
    "Externe_Organigramm_GV",
]
REF14_NAMES = {
    "docker-compose.yml", "compose.yaml", "compose.yml", "config.yaml",
    "custom_callback.py", "payload_scan.py", "tool_registry_gate.py",
    "mcp.registry.json", "CLAUDE.md", "settings.json", "settings.local.json",
}

TEXT_EXTS = {
    ".md", ".txt", ".json", ".jsonl", ".yaml", ".yml", ".csv", ".xml",
    ".log", ".toml", ".ini", ".cfg", ".conf", ".sh", ".zsh", ".py",
}
INDEXED_EXTS = TEXT_EXTS | {".docx", ".docm", ".pdf"}


def ensure_dirs():
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    (OUTPUT_ROOT / "TRANSFER_CANDIDATES/REF-06").mkdir(parents=True, exist_ok=True)
    (OUTPUT_ROOT / "TRANSFER_CANDIDATES/REF-12").mkdir(parents=True, exist_ok=True)


def canonical(path: Path) -> str:
    try:
        return str(path.resolve(strict=False))
    except Exception:
        return str(path)


def sha256(path: Path):
    try:
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


def stat_info(path: Path) -> dict:
    try:
        st = path.lstat()
        return {
            "size": st.st_size,
            "mtime": datetime.fromtimestamp(st.st_mtime).isoformat(),
            "is_symlink": stat.S_ISLNK(st.st_mode),
            "exists": True,
        }
    except Exception as e:
        return {"exists": False, "error": str(e)}


def should_prune_dir(path: Path) -> bool:
    parts = set(path.parts)
    if parts & PRUNE_NAMES:
        return True
    name = path.name.lower()
    if "verification_fixture" in name or "fixture" == name:
        return True
    if "level1" in name.lower() and "lineage" in name.lower():
        return True
    return False


def target_roots_existing():
    roots = [p for p in TARGET_ROOTS if p.exists()]
    roots.extend([p for p in EXTRA_DIRS if p.exists()])
    return roots


def is_under(path: Path, root: Path) -> bool:
    ps = str(path)
    rs = str(root)
    return ps == rs or ps.startswith(rs + "/")


def is_logish_or_project_evidence(path: Path) -> bool:
    ps = str(path)
    if any(x in ps for x in ["/.claude/", "/.codex/", "Application Support/Claude"]):
        return True
    if path == MAC_HOME / ".zsh_history":
        return True
    if is_under(path, WPNO_ROOT) and path.suffix.lower() in TEXT_EXTS:
        return True
    return False


def is_cloud_path(path: Path) -> bool:
    ps = str(path)
    return (
        "/Library/CloudStorage/" in ps
        or "/Library/Mobile Documents/com~apple~CloudDocs/" in ps
    )


def walk_files():
    seen = set()
    for root in target_roots_existing():
        for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
            dpath = Path(dirpath)
            if is_under(dpath, OUTPUT_ROOT):
                dirnames[:] = []
                continue
            dirnames[:] = [d for d in dirnames if not should_prune_dir(dpath / d)]
            if should_prune_dir(dpath):
                continue
            for fn in filenames:
                p = dpath / fn
                cp = canonical(p)
                if cp in seen:
                    continue
                seen.add(cp)
                yield p
    for p in EXTRA_FILES:
        if p.exists():
            yield p


def collect_targeted_files(spotlight):
    all_files = []
    docx_files = []
    targeted = {}
    filename_re = re.compile(
        r"(376|REF-12|L1-A29|BGH_REGISTER|Geschäftsverteilungsplan|Präsidium|Externe_Organigramm_GV|CLAUDE\.md|mcp\.registry|docker-compose|compose\.ya?ml|config\.ya?ml|custom_callback|payload_scan|tool_registry_gate)",
        re.I,
    )
    spotlight_paths = set()
    for values in spotlight.values():
        for raw in values:
            if raw.startswith("ERROR "):
                continue
            spotlight_paths.add(raw)
    for p in walk_files():
        all_files.append(p)
        suffix = p.suffix.lower()
        if suffix in {".docx", ".docm"}:
            if REF06_PRIORITIES.search(p.name):
                docx_files.append(p)
                targeted[canonical(p)] = p
        cp = canonical(p)
        if cp in spotlight_paths or str(p) in spotlight_paths:
            targeted[cp] = p
        elif is_logish_or_project_evidence(p) and suffix in INDEXED_EXTS and (not is_under(p, WPNO_ROOT) or filename_re.search(p.name) or p.name in REF14_NAMES):
            targeted[cp] = p
        elif filename_re.search(p.name) and suffix in INDEXED_EXTS:
            targeted[cp] = p
    selected = list(targeted.values())
    logish = []
    nonlog = []
    for p in selected:
        ps = str(p)
        if any(x in ps for x in ["/.claude/", "/.codex/", "Application Support/Claude"]) and p.name != ".zsh_history":
            logish.append(p)
        else:
            nonlog.append(p)
    def mt(p):
        try:
            return p.lstat().st_mtime
        except Exception:
            return 0
    logish = sorted(logish, key=mt, reverse=True)[:200]
    return all_files, docx_files, nonlog + logish


def text_from_docx(path: Path) -> str:
    chunks = []
    try:
        if is_cloud_path(path):
            return ""
        st = path.lstat()
        if st.st_size > 120 * 1024 * 1024:
            return ""
        with path.open("rb") as f:
            if f.read(4) != b"PK\x03\x04":
                return ""
        with zipfile.ZipFile(path) as z:
            for name in ("word/document.xml",):
                if name in z.namelist():
                    xml = z.read(name)
                    root = ET.fromstring(xml)
                    for elem in root.iter():
                        if elem.tag.endswith("}t") and elem.text:
                            chunks.append(elem.text)
                        elif elem.tag.endswith("}tab"):
                            chunks.append("\t")
                        elif elem.tag.endswith("}br") or elem.tag.endswith("}p"):
                            chunks.append("\n")
    except Exception:
        return ""
    return "".join(chunks)


def props_from_docx(path: Path) -> dict:
    out = {"valid_ooxml_zip": False, "app": {}, "core": {}, "zip_error": None}
    try:
        if is_cloud_path(path):
            out["zip_error"] = "skipped_deep_ooxml_read_cloud_path_no_download_attempted"
            return out
        st = path.lstat()
        if st.st_size > 120 * 1024 * 1024:
            out["zip_error"] = "skipped_deep_ooxml_read_size_over_120MiB"
            return out
        with path.open("rb") as f:
            if f.read(4) != b"PK\x03\x04":
                out["zip_error"] = "skipped_deep_ooxml_read_not_zip_magic"
                return out
        with zipfile.ZipFile(path) as z:
            names = set(z.namelist())
            out["valid_ooxml_zip"] = "[Content_Types].xml" in names and "word/document.xml" in names
            if "docProps/app.xml" in names:
                root = ET.fromstring(z.read("docProps/app.xml"))
                for child in root:
                    key = child.tag.split("}", 1)[-1]
                    out["app"][key] = child.text or ""
            if "docProps/core.xml" in names:
                root = ET.fromstring(z.read("docProps/core.xml"))
                for child in root:
                    key = child.tag.split("}", 1)[-1]
                    out["core"][key] = child.text or ""
    except Exception as e:
        out["zip_error"] = str(e)
    return out


def read_text(path: Path, max_bytes=2_000_000) -> str:
    try:
        if is_cloud_path(path):
            return ""
        with path.open("rb") as f:
            data = f.read(max_bytes)
        return data.decode("utf-8", errors="replace")
    except Exception:
        return ""


def pdf_text(path: Path, pages=2) -> str:
    # macOS often has pdftotext unavailable; strings is bounded and static.
    try:
        if is_cloud_path(path):
            return ""
        r = subprocess.run(["/usr/bin/strings", "-n", "6", str(path)], capture_output=True, text=True, timeout=15)
        return r.stdout[:20000]
    except Exception:
        return ""


def context_windows(text: str, term_re: re.Pattern, window=400):
    hits = []
    for m in term_re.finditer(text):
        start = max(0, m.start() - window)
        end = min(len(text), m.end() + window)
        hits.append({"match": m.group(0), "start": m.start(), "context": text[start:end]})
        if len(hits) >= 25:
            break
    return hits


def spotlight_search():
    results = defaultdict(list)
    queries = {
        "docx": 'kMDItemFSName == "*.docx"cd || kMDItemFSName == "*.docm"cd',
        "ref12": 'kMDItemTextContent == "*376*"cd || kMDItemFSName == "*376*"cd || kMDItemTextContent == "*REF-12*"cd || kMDItemTextContent == "*L1-A29*"cd',
        "ref05": 'kMDItemTextContent == "*BGH_REGISTER*"cd || kMDItemTextContent == "*Geschäftsverteilungsplan*"cd || kMDItemFSName == "*Externe_Organigramm_GV*"cd',
    }
    roots = [str(p) for p in target_roots_existing()]
    for label, query in queries.items():
        for root in roots:
            try:
                r = subprocess.run(["/usr/bin/mdfind", "-onlyin", root, query], capture_output=True, text=True, timeout=30)
                if r.returncode == 0:
                    results[label].extend([x for x in r.stdout.splitlines() if x.strip()])
            except Exception as e:
                results[label].append(f"ERROR {root}: {e}")
    return dict(results)


def find_l1a14_rule(files):
    term_re = re.compile(r"L1-A14|43 unique|citation-count|citation counting|Zitations", re.I)
    records = []
    for p in files:
        if p.suffix.lower() not in INDEXED_EXTS:
            continue
        text = ""
        if p.suffix.lower() in {".docx", ".docm"}:
            continue
        elif p.suffix.lower() == ".pdf":
            continue
        else:
            text = read_text(p, 500_000)
        if text and term_re.search(text):
            records.append({
                "path": canonical(p),
                "sha256": sha256(p),
                "contexts": context_windows(text, term_re, 700)[:5],
            })
            if len(records) >= 20:
                break
    return records


def classify_docx(path: Path, props: dict, text: str, log_refs: list, l1a14_found: bool):
    pages_raw = props.get("app", {}).get("Pages")
    try:
        pages = int(pages_raw) if pages_raw else None
    except ValueError:
        pages = None
    unique = sorted(set(m.group(0).strip() for m in BGH_CITE_RE.finditer(text)))
    occurrences = len(list(BGH_CITE_RE.finditer(text)))
    name_priority = bool(REF06_PRIORITIES.search(path.name))
    around_110 = pages is not None and 100 <= pages <= 120
    has_bgh = occurrences > 0
    original_hint = False
    for r in log_refs:
        ctx = r.get("context", "")
        if isinstance(ctx, list):
            ctx = "\n".join(str(x.get("context", "")) if isinstance(x, dict) else str(x) for x in ctx)
        if re.search(r"original|checker input|110.?page|43.?citation|L1-A14", str(ctx), re.I):
            original_hint = True
            break
    regen_hint = re.search(r"regenerated|resaved|converted from pdf|pdf conversion", text[:5000], re.I)
    if props.get("valid_ooxml_zip") and around_110 and len(unique) == 43 and original_hint and not regen_hint and l1a14_found:
        cls = "EXACT_MATCH"
    elif props.get("valid_ooxml_zip") and around_110 and (len(unique) >= 35 or original_hint or name_priority):
        cls = "STRONG_CANDIDATE"
    elif props.get("valid_ooxml_zip") and (name_priority or has_bgh or around_110):
        cls = "WEAK_CANDIDATE"
    else:
        cls = "NOT_REF06"
    return cls, unique, occurrences


def scan_logs_for_names(files, candidate_names):
    log_exts = TEXT_EXTS
    refs = defaultdict(list)
    general = re.compile(r"110.?page|43.?citation|L1-A14|original checker input|REF-06", re.I)
    for p in files:
        if p.suffix.lower() not in log_exts:
            continue
        if not is_logish_or_project_evidence(p):
            continue
        text = read_text(p, 500_000)
        if not text:
            continue
        if general.search(text):
            refs["__GENERAL_REF06__"].append({"path": canonical(p), "sha256": sha256(p), "context": context_windows(text, general, 350)[:5]})
    return refs


def ref12_scan(files):
    term_re = re.compile(r"376|REF-12|L1-A29|Independent 376 hash remeasurement", re.I)
    explicit_re = re.compile(r"(?i)(376\s+(?:refers to|means|is|denotes|=)|referent\s+of\s+376\s+(?:is|=)|REF-12[^.\n]{0,200}376)")
    records = []
    for p in files:
        if p.suffix.lower() not in INDEXED_EXTS:
            continue
        text = ""
        if p.suffix.lower() in {".docx", ".docm"}:
            continue
        elif p.suffix.lower() == ".pdf":
            text = pdf_text(p)
        else:
            text = read_text(p, 100_000)
        if not text or not term_re.search(text):
            continue
        if AUDIT_REPEAT_RE.search(text) and not explicit_re.search(text):
            continue
        contexts = context_windows(text, term_re, 650)
        defining = False
        for c in contexts:
            ctx = c["context"]
            if not explicit_re.search(ctx) or AUDIT_REPEAT_RE.search(ctx):
                continue
            if re.search(r"(?i)(An acceptable result must be|Do not accept:|Do not infer|Search especially:|For every relevant context record|If an explicit definition is found|Copy the actual artefact only)", ctx):
                continue
            if re.search(r"(?i)(not a filename|not a path|not defined|cannot be established|TARGET_MISSING|blocked on material|determine what 376 denotes|first establish exactly what 376 refers to)", ctx):
                continue
            defining = True
            break
        nearby_hashes = sorted(set(HEX64_RE.findall("\n".join(c["context"] for c in contexts))))
        records.append({
            "path": canonical(p),
            "sha256": sha256(p),
            "source_type": p.suffix.lower() or "file",
            "mtime": stat_info(p).get("mtime"),
            "explicitly_defines_referent": defining,
            "nearby_sha256_values": nearby_hashes[:20],
            "contexts": contexts[:12],
        })
    return records


def ref05_scan(files):
    term_re = re.compile("|".join(re.escape(t) for t in REF05_TERMS), re.I)
    records = []
    pdfs = []
    for p in files:
        suffix = p.suffix.lower()
        if suffix == ".pdf" and (re.search(r"BGH|Geschäftsverteilungsplan|Organigramm|GV|Präsidium", p.name, re.I)):
            pdfs.append(p)
        if suffix not in INDEXED_EXTS:
            continue
        text = ""
        if suffix in {".docx", ".docm"}:
            continue
        elif suffix == ".pdf":
            text = pdf_text(p)
        else:
            text = read_text(p, 100_000)
        if text and term_re.search(text):
            records.append({
                "path": canonical(p),
                "sha256": sha256(p),
                "source_type": suffix or "file",
                "contexts": context_windows(text, term_re, 600)[:12],
            })
    return records, pdfs


def mdls_xattrs(path: Path):
    out = {"where_froms": None, "quarantine": None, "mdls": {}}
    try:
        if is_cloud_path(path):
            out["cloud_path_note"] = "content/xattr reads avoided to prevent cloud download"
            return out
        r = subprocess.run(["/usr/bin/mdls", "-plist", "-", str(path)], capture_output=True, timeout=10)
        if r.returncode == 0 and r.stdout:
            plist = plistlib.loads(r.stdout)
            for k in ("kMDItemTitle", "kMDItemAuthors", "kMDItemCreator", "kMDItemContentCreationDate", "kMDItemWhereFroms"):
                if k in plist:
                    out["mdls"][k] = str(plist[k])
            out["where_froms"] = str(plist.get("kMDItemWhereFroms")) if "kMDItemWhereFroms" in plist else None
    except Exception as e:
        out["mdls_error"] = str(e)
    try:
        r = subprocess.run(["/usr/bin/xattr", "-p", "com.apple.quarantine", str(path)], capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            out["quarantine"] = r.stdout.strip()
    except Exception as e:
        out["xattr_error"] = str(e)
    return out


def docx_mdls_props(path: Path) -> dict:
    props = {"valid_ooxml_zip": False, "app": {}, "core": {}, "zip_error": "metadata_only_no_deep_ooxml_read"}
    try:
        r = subprocess.run(
            ["/usr/bin/mdls", "-raw", "-name", "kMDItemNumberOfPages", "-name", "kMDItemAuthors", "-name", "kMDItemTitle", "-name", "kMDItemContentCreationDate", "-name", "kMDItemContentModificationDate", str(path)],
            capture_output=True,
            text=True,
            timeout=5,
        )
        vals = [x.strip() for x in r.stdout.splitlines()]
        if len(vals) >= 1 and vals[0] not in {"(null)", ""}:
            props["app"]["Pages"] = vals[0]
        if len(vals) >= 2 and vals[1] not in {"(null)", ""}:
            props["core"]["creator"] = vals[1]
        if len(vals) >= 3 and vals[2] not in {"(null)", ""}:
            props["core"]["title"] = vals[2]
        if len(vals) >= 4 and vals[3] not in {"(null)", ""}:
            props["core"]["created"] = vals[3]
        if len(vals) >= 5 and vals[4] not in {"(null)", ""}:
            props["core"]["modified"] = vals[4]
    except Exception as e:
        props["zip_error"] = f"metadata_only_mdls_error:{e}"
    return props


def ref14_inventory(files):
    relevant = []
    referenced = set()
    for p in files:
        if p == MAC_HOME / ".claude/CLAUDE.md":
            relevant.append((p, "global_claude_md", None))
        if WPNO_ROOT in p.parents and p.name in REF14_NAMES:
            if p.name == "CLAUDE.md" or "/docker/" in str(p) or "/mcp/" in str(p) or p.parent == WPNO_ROOT:
                relevant.append((p, "wpno_config_or_claude", None))
    # Add simple referenced config paths from already relevant text files.
    for p, _, _ in list(relevant):
        if p.suffix.lower() in TEXT_EXTS or p.name in REF14_NAMES:
            text = read_text(p, 300_000)
            for m in re.finditer(r"(?:(?:\./|\../|/Users/)[A-Za-z0-9_./~ -]+\.(?:json|ya?ml|py|md|toml|ini|conf))", text):
                raw = m.group(0).strip().strip("'\"")
                rp = Path(raw).expanduser()
                if not rp.is_absolute():
                    rp = (p.parent / rp)
                if rp.exists() and WPNO_ROOT in rp.parents:
                    referenced.add((rp, p))
    for rp, referrer in referenced:
        relevant.append((rp, "referenced_config", referrer))
    dedup = {}
    for p, role, referrer in relevant:
        dedup[canonical(p)] = (p, role, referrer)
    records = []
    for cp, (p, role, referrer) in sorted(dedup.items()):
        info = stat_info(p)
        text = read_text(p, 300_000) if (p.suffix.lower() in TEXT_EXTS or p.name in REF14_NAMES) else ""
        records.append({
            "canonical_path": cp,
            "file_type": p.suffix.lower() or p.name,
            "size": info.get("size"),
            "sha256": sha256(p),
            "is_symlink": info.get("is_symlink"),
            "mtime": info.get("mtime"),
            "role": role,
            "referring_file": canonical(referrer) if referrer else None,
            "contains_secret_bearing_field_names": bool(SECRET_FIELD_RE.search(text)),
        })
    return records


def session_metadata_scan(files):
    cwd_re = re.compile(r'"(?:cwd|current_dir|working_directory|project_root)"\s*:\s*"([^"]+)"|(?:cwd|project root|working directory)[:=]\s*([^\n\r]+)', re.I)
    claude_re = re.compile(r"CLAUDE\.md|/\.claude/|WPNO|working directory|cwd|project_root", re.I)
    records = []
    external_dirs = {}
    for p in files:
        if p.suffix.lower() not in TEXT_EXTS and p.name not in {".zsh_history"}:
            continue
        ps = str(p)
        if not any(x in ps for x in [".claude", ".codex", "Application Support/Claude", ".zsh_history"]):
            continue
        text = read_text(p, 100_000)
        if not text or not claude_re.search(text):
            continue
        contexts = context_windows(text, claude_re, 450)[:20]
        dirs = []
        for m in cwd_re.finditer(text):
            d = (m.group(1) or m.group(2) or "").strip().strip('"')
            if d:
                dirs.append(d)
        records.append({
            "path": canonical(p),
            "sha256": sha256(p),
            "mtime": stat_info(p).get("mtime"),
            "cwd_or_project_values": dirs[:50],
            "contexts": contexts[:10],
        })
        for d in dirs:
            dp = Path(d).expanduser()
            if not dp.is_absolute():
                continue
            try:
                cdp = dp.resolve(strict=False)
            except Exception:
                cdp = dp
            if str(cdp).startswith(str(WPNO_ROOT)):
                continue
            if str(cdp).startswith(str(MAC_HOME)):
                key = str(cdp)
                external_dirs.setdefault(key, {
                    "canonical_path": key,
                    "evidence_sources": [],
                })
                external_dirs[key]["evidence_sources"].append({
                    "source": canonical(p),
                    "source_sha256": sha256(p),
                    "timestamp": stat_info(p).get("mtime"),
                })
    return records, list(external_dirs.values())


def bounded_dir_count(path: Path):
    count = 0
    total = 0
    truncated = False
    try:
        for dirpath, dirnames, filenames in os.walk(path, topdown=True, followlinks=False):
            dpath = Path(dirpath)
            dirnames[:] = [d for d in dirnames if not should_prune_dir(dpath / d)]
            for fn in filenames:
                try:
                    st = (dpath / fn).lstat()
                    count += 1
                    total += st.st_size
                except Exception:
                    pass
                if count >= 2000:
                    truncated = True
                    raise StopIteration
    except StopIteration:
        pass
    except Exception:
        pass
    return count, total, truncated


def write_json(path: Path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def write_reports(data):
    # REF06 CSV
    with (OUTPUT_ROOT / "REF06_CANDIDATES.csv").open("w", newline="", encoding="utf-8") as f:
        fields = ["classification", "path", "size", "sha256", "is_symlink", "valid_ooxml_zip", "pages", "words", "characters", "creator", "created", "modified", "title", "unique_citation_count", "total_citation_occurrences", "log_reference_count"]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in data["ref06_candidates"]:
            w.writerow({k: r.get(k) for k in fields})

    # REF12 contexts
    lines = ["# REF-12 / 376 Contexts", ""]
    if not data["ref12_records"]:
        lines.append("No relevant contexts found.")
    for i, r in enumerate(data["ref12_records"], 1):
        lines += [
            f"## Context {i}",
            f"- Source: `{r['path']}`",
            f"- SHA-256: `{r['sha256']}`",
            f"- Type: `{r['source_type']}`",
            f"- Explicitly defines referent: `{r['explicitly_defines_referent']}`",
            f"- Nearby SHA-256 values: `{', '.join(r['nearby_sha256_values']) if r['nearby_sha256_values'] else 'none'}`",
            "",
        ]
        for c in r["contexts"][:5]:
            lines.append("```text")
            lines.append(c["context"].replace("\x00", " ")[:1400])
            lines.append("```")
    (OUTPUT_ROOT / "REF12_376_CONTEXTS.md").write_text("\n".join(lines), encoding="utf-8")

    # REF05 report
    lines = ["# REF-05 Period And Provenance Report", ""]
    lines.append(f"Classification: `{data['ref05_status']}`")
    lines.append(f"Organigram classification: `{data['organigram_status']}`")
    lines.append("")
    lines.append("## Period Evidence")
    if not data["ref05_records"]:
        lines.append("No explicit BGH_REGISTER validity-period source found in targeted roots.")
    for r in data["ref05_records"]:
        lines += [f"### {r['path']}", f"- SHA-256: `{r['sha256']}`", ""]
        for c in r["contexts"][:4]:
            lines.append("```text")
            lines.append(c["context"].replace("\x00", " ")[:1200])
            lines.append("```")
    lines.append("## BGH PDF Evidence")
    for r in data["bgh_pdfs"]:
        lines += [
            f"### {r['path']}",
            f"- SHA-256: `{r['sha256']}`",
            f"- Size: `{r['size']}`",
            f"- Title/provenance metadata: `{json.dumps(r['metadata'], ensure_ascii=False)[:1000]}`",
            f"- Inferred issuer from content/provenance: `{r['issuer_inference']}`",
            "",
        ]
    (OUTPUT_ROOT / "REF05_PERIOD_AND_PROVENANCE_REPORT.md").write_text("\n".join(lines), encoding="utf-8")

    write_json(OUTPUT_ROOT / "REF14_MAC_REALITY.json", data["ref14"])
    lines = ["# REF-14 / L1-A23 Mac Reality", ""]
    lines.append(f"REF14_L1_A17_STATUS: `{data['ref14']['l1_a17_status']}`")
    lines.append(f"REF14_L1_A23_STATUS: `{data['ref14']['l1_a23_status']}`")
    lines.append("")
    lines.append("## Files")
    for r in data["ref14"]["files"]:
        lines.append(f"- `{r['canonical_path']}` | role `{r['role']}` | sha256 `{r['sha256']}` | symlink `{r['is_symlink']}` | secret field names `{r['contains_secret_bearing_field_names']}`")
    lines.append("")
    lines.append("## Session Metadata")
    for r in data["ref14"]["session_metadata"][:30]:
        lines.append(f"- `{r['path']}` | sha256 `{r['sha256']}` | cwd/project values `{len(r['cwd_or_project_values'])}`")
    (OUTPUT_ROOT / "REF14_MAC_REALITY.md").write_text("\n".join(lines), encoding="utf-8")

    write_json(OUTPUT_ROOT / "L1_A24_EXTERNAL_DIRECTORY_CANDIDATES.json", data["external_dirs"])
    lines = ["L1-A24 human decision template", "", "Do not approve a launch directory without human review.", ""]
    for r in data["external_dirs"]:
        lines += [
            f"Candidate: {r['canonical_path']}",
            f"Evidence sources: {len(r['evidence_sources'])}",
            "Human decision: ACCEPT / REJECT / NEEDS_MORE_REVIEW",
            "Reason:",
            "",
        ]
    if not data["external_dirs"]:
        lines.append("No evidence-backed external launch-directory candidates found.")
    (OUTPUT_ROOT / "L1_A24_HUMAN_DECISION_TEMPLATE.txt").write_text("\n".join(lines), encoding="utf-8")

    # Main status JSON/report.
    write_json(OUTPUT_ROOT / "MAC_EVIDENCE_STATUS.json", data["status"])
    lines = [
        "# Mac Evidence Search Report",
        "",
        f"Run timestamp: `{data['run_timestamp']}`",
        f"Mode: `READ_ONLY_TARGETED_MAC_EVIDENCE_SEARCH`",
        f"Network used: `NO`",
        f"Source files modified: `NO`",
        f"WPNO modified: `NO`",
        "",
        "## Status",
        f"- REF06_STATUS: `{data['status']['REF06_STATUS']}`",
        f"- REF12_STATUS: `{data['status']['REF12_STATUS']}`",
        f"- REF05_VALIDITY_PERIOD_STATUS: `{data['status']['REF05_VALIDITY_PERIOD_STATUS']}`",
        f"- REF05_ORGANIGRAM_STATUS: `{data['status']['REF05_ORGANIGRAM_STATUS']}`",
        f"- REF14_L1_A17_STATUS: `{data['status']['REF14_L1_A17_STATUS']}`",
        f"- REF14_L1_A23_STATUS: `{data['status']['REF14_L1_A23_STATUS']}`",
        f"- L1_A24_CANDIDATE_COUNT: `{data['status']['L1_A24_CANDIDATE_COUNT']}`",
        "",
        "## Notes",
        f"- Spotlight result buckets: `{ {k: len(v) for k, v in data['spotlight'].items()} }`",
        f"- L1-A14 rule evidence files found: `{len(data['l1a14_rule_records'])}`",
        "- Secret-bearing field names are reported as booleans only; values are not printed.",
    ]
    (OUTPUT_ROOT / "MAC_EVIDENCE_SEARCH_REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def transfer_manifest():
    lines = []
    tc = OUTPUT_ROOT / "TRANSFER_CANDIDATES"
    for p in sorted(tc.rglob("*")):
        if p.is_file():
            lines.append(f"{sha256(p)}  {p.relative_to(OUTPUT_ROOT)}")
    (OUTPUT_ROOT / "TRANSFER_CANDIDATES.sha256").write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def main():
    ensure_dirs()
    run_ts = datetime.now(timezone.utc).isoformat()
    spotlight = spotlight_search()
    all_files, docx_files, files = collect_targeted_files(spotlight)

    l1a14_records = find_l1a14_rule(files)
    name_refs = defaultdict(list)

    ref06 = []
    for p in docx_files:
        info = stat_info(p)
        deep_docx = False
        props = {"valid_ooxml_zip": False, "app": {}, "core": {}, "zip_error": "path_inventory_only_no_deep_read"}
        text = text_from_docx(p) if (deep_docx and props.get("valid_ooxml_zip")) else ""
        log_refs = name_refs.get(p.name, []) + name_refs.get("__GENERAL_REF06__", [])
        cls, unique, occ = classify_docx(p, props, text, log_refs, bool(l1a14_records))
        candidate_hash = None
        if False:
            candidate_hash = sha256(p)
        ref06.append({
            "classification": cls,
            "path": canonical(p),
            "size": info.get("size"),
            "sha256": candidate_hash,
            "is_symlink": info.get("is_symlink"),
            "valid_ooxml_zip": props.get("valid_ooxml_zip"),
            "pages": props.get("app", {}).get("Pages"),
            "words": props.get("app", {}).get("Words"),
            "characters": props.get("app", {}).get("Characters"),
            "creator": props.get("core", {}).get("creator") or props.get("core", {}).get("lastModifiedBy"),
            "created": props.get("core", {}).get("created"),
            "modified": props.get("core", {}).get("modified"),
            "title": props.get("core", {}).get("title"),
            "unique_citation_count": len(unique),
            "total_citation_occurrences": occ,
            "log_reference_count": len(log_refs),
            "sample_unique_citations": unique[:20],
        })

    exact = [r for r in ref06 if r["classification"] == "EXACT_MATCH"]
    ref06_exact_path = None
    if len(exact) == 1:
        src = Path(exact[0]["path"])
        dst = OUTPUT_ROOT / "TRANSFER_CANDIDATES/REF-06" / src.name
        shutil.copy2(src, dst, follow_symlinks=False)
        src_hash = sha256(src)
        dst_hash = sha256(dst)
        prov = {
            "source_path": exact[0]["path"],
            "copied_path": canonical(dst),
            "source_sha256": src_hash,
            "copied_sha256": dst_hash,
            "hashes_identical": src_hash == dst_hash,
            "classification_basis": exact[0],
        }
        write_json(OUTPUT_ROOT / "TRANSFER_CANDIDATES/REF-06/REF-06_OPERATOR_PROVENANCE_DRAFT.json", prov)
        (OUTPUT_ROOT / "TRANSFER_CANDIDATES/REF-06/REF-06_MANIFEST.sha256").write_text(f"{dst_hash}  {dst.name}\n", encoding="utf-8")
        ref06_exact_path = exact[0]["path"]

    ref12 = ref12_scan(files)
    explicit_ref12 = [r for r in ref12 if r["explicitly_defines_referent"]]
    ref12_status = "NOT_FOUND"
    ref12_source = None
    ref12_artifact = None
    ref12_hash_prov = "NOT_APPLICABLE"
    if explicit_ref12:
        ref12_status = "EXPLICIT_DEFINITION_FOUND"
        ref12_source = explicit_ref12[0]["path"]
        definition_text = explicit_ref12[0]["contexts"][0]["context"] if explicit_ref12[0]["contexts"] else ""
        (OUTPUT_ROOT / "TRANSFER_CANDIDATES/REF-12/REF-12-376-definition-source.txt").write_text(definition_text, encoding="utf-8")
        (OUTPUT_ROOT / "TRANSFER_CANDIDATES/REF-12/REF-12-376-definition-draft.txt").write_text(
            "Explicit definition context found. Human review required before treating any artefact as unambiguous.\n\n" + definition_text,
            encoding="utf-8",
        )
        src_hash = sha256(Path(ref12_source))
        (OUTPUT_ROOT / "TRANSFER_CANDIDATES/REF-12/REF-12_CONTEXT_EVIDENCE.sha256").write_text(f"{src_hash}  {ref12_source}\n", encoding="utf-8")
        ref12_hash_prov = "MISSING"
    elif ref12:
        ref12_status = "CONTEXTS_FOUND_BUT_NO_DEFINITION"

    ref05_records, bgh_pdf_paths = ref05_scan(files)
    bgh_pdfs = []
    organigram_status = "ORGANIGRAM_UNRELATED"
    validity_status = "PERIOD_NOT_FOUND"
    validity_value = None
    period_re = re.compile(r"(?i)(?:validity period|Gültigkeitszeitraum|Stichtag|as of|Stand:)[^\n\r]{0,180}")
    for r in ref05_records:
        pm = None
        for c in r["contexts"]:
            ctx = c.get("context", "")
            if re.search(r"CURRENT REMAINING MAC-SEARCHABLE ITEMS|Evidence defining:|Search specifically for:|Read original project files and AI session logs|Determine whether any source explicitly states|Do not assume it is a BGH publication", ctx, re.I):
                continue
            if re.search(r"BGH_REGISTER", ctx, re.I):
                pm = period_re.search(ctx)
                if pm:
                    break
        if pm:
            validity_status = "PERIOD_EXPLICITLY_FOUND"
            validity_value = pm.group(0).strip()
            break
    for p in sorted(set(bgh_pdf_paths), key=lambda x: str(x)):
        meta = mdls_xattrs(p)
        text = pdf_text(p)
        issuer = "unknown"
        if re.search(r"Bundesgerichtshof|www\.bundesgerichtshof\.de|bgh\.bund\.de", text + json.dumps(meta), re.I):
            issuer = "Bundesgerichtshof evidence present"
        elif re.search(r"Organigramm|Externe_Organigramm_GV", p.name, re.I):
            issuer = "issuer not proven from bounded content/provenance"
        if p.name == "2026_07_01_Externe_Organigramm_GV.pdf":
            if issuer == "Bundesgerichtshof evidence present":
                organigram_status = "ORGANIGRAM_OFFICIAL_SOURCE_PROVEN"
            else:
                organigram_status = "ORGANIGRAM_SOURCE_UNPROVEN"
        st = stat_info(p)
        bgh_pdfs.append({
            "path": canonical(p),
            "sha256": None if is_cloud_path(p) else sha256(p),
            "size": st.get("size"),
            "metadata": meta,
            "issuer_inference": issuer,
        })

    ref14_files = ref14_inventory(files)
    session_records, external_dirs = session_metadata_scan(files)
    for r in external_dirs:
        p = Path(r["canonical_path"])
        exists = p.exists()
        count, total, truncated = bounded_dir_count(p) if exists and p.is_dir() else (0, 0, False)
        r.update({
            "directory_exists": exists,
            "directory_symlink_status": stat_info(p).get("is_symlink") if exists else None,
            "expected_global_CLAUDE_md_path": str(MAC_HOME / ".claude/CLAUDE.md"),
            "project_CLAUDE_md_exists": (p / "CLAUDE.md").exists() if exists and p.is_dir() else False,
            "bounded_file_count": count,
            "bounded_total_size": total,
            "bounded_count_truncated": truncated,
            "why_may_be_relevant": "Session metadata or shell history records this directory as a Claude/Codex cwd outside WPNO_ROOT.",
        })

    l1_a17 = "REF14_L1_A17_MAC_SUPPORT" if any("/docker/" in r["canonical_path"] or "/mcp/" in r["canonical_path"] for r in ref14_files) else "REF14_L1_A17_MAC_SUPPORT_MISSING"
    l1_a23 = "REF14_L1_A23_MAC_REALITY_COMPLETE" if ref14_files and session_records else "REF14_L1_A23_MAC_REALITY_PARTIAL"
    ref14 = {
        "files": ref14_files,
        "crosswalk": [
            {
                "current_mac_source_path": r["canonical_path"],
                "expected_deployment_role": r["role"],
                "container_destination_where_known": None,
                "relation_to_WPNO_docker": "inside WPNO/docker" if "/docker/" in r["canonical_path"] else None,
                "relation_to_WPNO_mcp": "inside WPNO/mcp" if "/mcp/" in r["canonical_path"] else None,
                "current_sha256": r["sha256"],
                "production_identity_status": "measured_on_mac_not_proven_production",
            }
            for r in ref14_files
        ],
        "session_metadata": session_records,
        "l1_a17_status": l1_a17,
        "l1_a23_status": l1_a23,
    }

    ref06_status = "EXACT_MATCH_FOUND" if len(exact) == 1 else ("CANDIDATES_FOUND" if any(r["classification"] in {"STRONG_CANDIDATE", "WEAK_CANDIDATE"} for r in ref06) else "NOT_FOUND")
    final_status = "MAC_EVIDENCE_FOUND" if ref06_status == "EXACT_MATCH_FOUND" and ref12_status == "EXPLICIT_DEFINITION_FOUND" and validity_status == "PERIOD_EXPLICITLY_FOUND" else ("MAC_EVIDENCE_PARTIAL" if ref06_status != "NOT_FOUND" or ref12_status != "NOT_FOUND" or validity_status == "PERIOD_EXPLICITLY_FOUND" or ref14_files or external_dirs else "MAC_EVIDENCE_NOT_FOUND")

    status = {
        "REF06_STATUS": ref06_status,
        "REF06_EXACT_MATCH_PATH": ref06_exact_path,
        "REF12_STATUS": ref12_status,
        "REF12_DEFINITION_SOURCE": ref12_source,
        "REF12_ARTEFACT_PATH": ref12_artifact,
        "REF12_EXPECTED_HASH_PROVENANCE": ref12_hash_prov,
        "REF05_VALIDITY_PERIOD_STATUS": "FOUND" if validity_status == "PERIOD_EXPLICITLY_FOUND" else "NOT_FOUND",
        "REF05_VALIDITY_PERIOD": validity_value,
        "REF05_ORGANIGRAM_STATUS": organigram_status,
        "REF14_L1_A17_STATUS": l1_a17,
        "REF14_L1_A23_STATUS": l1_a23,
        "L1_A24_CANDIDATE_COUNT": len(external_dirs),
        "SOURCE_FILES_MODIFIED": "NO",
        "WPNO_MODIFIED": "NO",
        "NETWORK_USED": "NO",
        "OUTPUT_ROOT": str(OUTPUT_ROOT),
        "NEXT_REQUIRED_ACTION": "Review generated candidate/context reports and make a human decision on unresolved evidence." if final_status != "MAC_EVIDENCE_FOUND" else "Transfer the exact matched evidence artefacts with generated manifests.",
        "FINAL_STATUS": final_status,
    }

    data = {
        "run_timestamp": run_ts,
        "spotlight": spotlight,
        "l1a14_rule_records": l1a14_records,
        "ref06_candidates": sorted(ref06, key=lambda r: ({"EXACT_MATCH": 0, "STRONG_CANDIDATE": 1, "WEAK_CANDIDATE": 2, "NOT_REF06": 3}[r["classification"]], r["path"])),
        "ref12_records": ref12,
        "ref05_records": ref05_records,
        "bgh_pdfs": bgh_pdfs,
        "ref05_status": validity_status,
        "organigram_status": organigram_status,
        "ref14": ref14,
        "external_dirs": external_dirs,
        "status": status,
    }

    write_reports(data)
    transfer_manifest()

    print("R7 MAC MISSING-EVIDENCE SEARCH COMPLETE")
    print()
    for key in [
        "REF06_STATUS",
        "REF06_EXACT_MATCH_PATH",
        "REF12_STATUS",
        "REF12_DEFINITION_SOURCE",
        "REF12_ARTEFACT_PATH",
        "REF12_EXPECTED_HASH_PROVENANCE",
        "REF05_VALIDITY_PERIOD_STATUS",
        "REF05_VALIDITY_PERIOD",
        "REF05_ORGANIGRAM_STATUS",
        "REF14_L1_A17_STATUS",
        "REF14_L1_A23_STATUS",
        "L1_A24_CANDIDATE_COUNT",
        "SOURCE_FILES_MODIFIED",
        "WPNO_MODIFIED",
        "NETWORK_USED",
        "OUTPUT_ROOT",
        "NEXT_REQUIRED_ACTION",
        "FINAL_STATUS",
    ]:
        print(f"{key}:")
        value = status[key]
        print(value if value is not None else "null")


if __name__ == "__main__":
    main()
