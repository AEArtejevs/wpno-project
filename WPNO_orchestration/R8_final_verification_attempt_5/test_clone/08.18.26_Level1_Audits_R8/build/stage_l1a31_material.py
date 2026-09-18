#!/usr/bin/env python3
"""Stage L1-A31's certificate material and controls for R7.

Nothing here is acquired. Every real certificate is carried forward from R6's
staged set byte-for-byte and the equality is proved by digest, because R6's
acquisition, P7S parsing and certificate extraction were completed and must
not be repeated.

Two things are new.

First, each staged CA certificate is additionally checked, in DER, against the
operator-supplied official chain material. That material is not used as the
source — the source is still R6's staged bytes — it is used as an independent
second opinion on what those bytes are. If the two ever disagreed, that would
be a finding, and it would surface here rather than inside an audit run.

Second, the control fixtures are rebuilt. R6's were the reason its RUN-A
sealed an ERROR:

  * its synthetic positive-control chain carried clientAuth only, so it could
    never satisfy the `-purpose smimesign` its own plan asked for;
  * its synthetic validation epoch, 1787000000, was six days and eighteen
    hours before the synthetic root's own notBefore;
  * its certificate mutation was a base64 flip that produced a file OpenSSL
    would not load, so it proved a parse refusal and not a signature failure.

The synthetic chain is therefore rebuilt from `automation.tests.support.
synthetic_chain`, which issues a leaf carrying emailProtection and derives its
validation time from the moment of issue rather than from a literal. The
mutations are rebuilt by `automation.mutation_fixtures`, which proves each one
did what it claims before returning it.
"""

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from automation import (hashing, mutation_fixtures, path_policy,  # noqa: E402
                        policy, trust_material)
from automation.tests.support import synthetic_chain                    # noqa: E402

# R8 carries no physical copy of the inherited lineage tree: R7's is 555 MiB
# and duplicating it would buy nothing a hash does not already give. The R6
# staged bytes are therefore read through R7's lineage, in place and
# read-only, and `carry_forward` proves byte equality by digest exactly as it
# did when the tree was local. The path is absolute and sits under
# PROJECT_ROOT, so `path_policy` admits it for reading and refuses it for
# writing.
R6_STAGED_VIA_R7_LINEAGE = os.path.join(
    os.path.dirname(ROOT), "08.18.26_Level1_Audits_R7", "lineage",
    "R6_EXECUTION", "work", "L1-A31", "preparation_2026-08-26", "staged")
R6_STAGED_LOCAL = os.path.join(
    ROOT, "lineage", "R6_EXECUTION", "work", "L1-A31",
    "preparation_2026-08-26", "staged")
R6_STAGED = (R6_STAGED_LOCAL if os.path.isdir(R6_STAGED_LOCAL)
             else R6_STAGED_VIA_R7_LINEAGE)
# Operator-supplied official chain material. It arrives from outside
# PROJECT_ROOT, so it is taken in through the operator-intake route before it
# is read: the package's own path policy refuses to hash a file outside its
# roots, and rightly — a control that reads whatever path it is handed is not
# a control. The source directory is read once, here, with plain file I/O and
# no interpretation, and everything afterwards works from the intake copy.
OFFICIAL_SOURCE = "/home/ubuntu/project/2026-08-21_L1-A31_Official_Chain_Material"
OFFICIAL_MEMBERS = (
    "2021-09-09-bea-vhn-ca-2017.crt",
    "2021-09-09-bea-vhn-ca-2017.pem",
    "2021-09-09-safe-root-ca-2017.crt.der",
    "BNotK_rqSigt_CA_2020.cer",
    "TL-DE.XML",
    "TL-DE.sha2.txt",
    "bnotkrootca2017.crt",
)
INTAKE = os.path.join(ROOT, "work", "operator_intake", "L1-A31",
                      "official_chain_material_r7_2026-08-26")
OFFICIAL = INTAKE

PREPARATION = os.path.join(ROOT, "work", "L1-A31", "preparation_r8_2026-08-28")
CERTS = os.path.join(PREPARATION, "certs")
CONTROLS = os.path.join(PREPARATION, "controls")
SYNTHETIC = os.path.join(PREPARATION, "synthetic")
STAGED_ANCHORS = os.path.join(PREPARATION, "staged_anchors")

# The real certificates, carried forward. Names unchanged so the lineage of
# each file is legible without a mapping table.
CARRY = (
    "vhn_leaf_from_sealed_p7s_parse_evidence.pem",
    "vhn_intermediate_selected_manual_pem.pem",
    "vhn_intermediate_unselected_duplicate_crt.pem",
    "vhn_root.pem",
    "document_leaf_from_sealed_p7s_parse_evidence.pem",
    "document_intermediate.pem",
    "document_root.pem",
)

# Which staged certificate each officially supplied file should equal, in DER.
# The supplied set covers the four CA certificates. The two leaves are not in
# it: they come out of the signed containers themselves, which is where a
# signer certificate belongs.
OFFICIAL_EQUIVALENCE = {
    "vhn_intermediate_selected_manual_pem.pem": (
        "2021-09-09-bea-vhn-ca-2017.pem", "PEM"),
    "vhn_root.pem": ("2021-09-09-safe-root-ca-2017.crt.der", "DER"),
    "document_intermediate.pem": ("BNotK_rqSigt_CA_2020.cer", "DER"),
    "document_root.pem": ("bnotkrootca2017.crt", "DER"),
}


def run(argv, cwd):
    return subprocess.run(  # noqa: S603 - argv list, shell=False
        argv, shell=False, capture_output=True, timeout=120,
        env=policy.base_environment(), cwd=cwd, check=False)


def der_digest(path, form):
    proc = run([policy.EXECUTABLES["openssl"], "x509", "-in", path,
                "-inform", form, "-outform", "DER"], os.path.dirname(path))
    if proc.returncode != 0:
        raise SystemExit("cannot read %s as %s: %s"
                         % (path, form, proc.stderr.decode("utf-8", "replace")))
    return hashing.sha256_bytes(proc.stdout)


def take_in_official_material():
    """Copy the operator's official chain material into the package, once.

    Digests are taken on both sides with the standard library rather than
    through `hashing`, because the source is outside PROJECT_ROOT and
    `hashing` refuses such a path by design. From the moment the copy lands
    inside `work/operator_intake/`, every later read goes through the normal
    policy-checked path.

    TL-DE.XML carries its own published digest in TL-DE.sha2.txt. That is
    checked here, not asserted: a trusted list that does not match its own
    published digest is not evidence of anything.
    """
    import hashlib

    def digest(path):
        h = hashlib.sha256()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()

    os.makedirs(INTAKE, exist_ok=True)
    members = []
    for name in OFFICIAL_MEMBERS:
        source = os.path.join(OFFICIAL_SOURCE, name)
        if not os.path.isfile(source):
            members.append({"name": name, "result": "ABSENT_AT_SOURCE"})
            continue
        destination = os.path.join(INTAKE, name)
        source_digest = digest(source)
        with open(source, "rb") as src, open(destination, "wb") as dst:
            while True:
                chunk = src.read(1 << 20)
                if not chunk:
                    break
                dst.write(chunk)
        copy_digest = digest(destination)
        if source_digest != copy_digest:
            raise SystemExit("intake digest mismatch: %s" % name)
        members.append({
            "name": name,
            "source": os.path.join(OFFICIAL_SOURCE, name),
            "path": os.path.relpath(destination, ROOT),
            "sha256": copy_digest,
            "bytes": os.path.getsize(destination),
        })

    # The trusted list against its own published digest.
    tl_result = {"checked": False}
    tl_xml = os.path.join(INTAKE, "TL-DE.XML")
    tl_sha = os.path.join(INTAKE, "TL-DE.sha2.txt")
    if os.path.isfile(tl_xml) and os.path.isfile(tl_sha):
        with open(tl_sha, encoding="utf-8") as handle:
            published = handle.read().split()[0].strip().lower()
        measured = digest(tl_xml)
        tl_result = {
            "checked": True,
            "published_digest": published,
            "measured_digest": measured,
            "matches": published == measured,
        }

    return {
        "source_directory": OFFICIAL_SOURCE,
        "intake_directory": os.path.relpath(INTAKE, ROOT),
        "members": members,
        "trusted_list_self_check": tl_result,
        "supplied_by": "operator, during the R7 build",
        "used_as": ("an independent second opinion on the identity of the "
                    "staged CA certificates; NOT as the source of any staged "
                    "byte, which remains R6's completed acquisition"),
    }


def carry_forward():
    """Copy R6's staged certificates and prove each copy by digest."""
    records = []
    for name in CARRY:
        source = os.path.join(R6_STAGED, "certs", name)
        destination = os.path.join(CERTS, name)
        before = hashing.sha256_file(source)
        with open(source, "rb") as src, open(destination, "wb") as dst:
            dst.write(src.read())
        after = hashing.sha256_file(destination)
        if before != after:
            raise SystemExit("carry-forward digest mismatch: %s" % name)
        records.append({
            "name": name,
            "source": os.path.relpath(source, ROOT),
            "path": os.path.relpath(destination, ROOT),
            "sha256": after,
            "byte_identical_to_r6": True,
        })
    return records


def cross_check_official():
    """Compare each staged CA against the operator-supplied official file."""
    results = []
    for staged_name, (official_name, form) in sorted(
            OFFICIAL_EQUIVALENCE.items()):
        staged = os.path.join(CERTS, staged_name)
        official = os.path.join(OFFICIAL, official_name)
        if not os.path.isfile(official):
            results.append({"staged": staged_name, "official": official_name,
                            "result": "OFFICIAL_FILE_ABSENT"})
            continue
        staged_der = der_digest(staged, "PEM")
        # `official` now names the intake copy inside the package, so the
        # policy-checked hashing path applies to it like anything else.
        official_der = der_digest(official, form)
        results.append({
            "staged": staged_name,
            "official": official_name,
            "official_file_sha256": hashing.sha256_file(official),
            "staged_der_sha256": staged_der,
            "official_der_sha256": official_der,
            "identical_in_der": staged_der == official_der,
            "result": "EQUAL" if staged_der == official_der else "DIFFERENT",
        })
    return results


def build_controls():
    """Rebuild the synthetic chain and every mutation fixture, with proofs."""
    fixture = synthetic_chain.build(SYNTHETIC)

    # The synthetic control's validation time is derived from the certificates
    # that were just issued, not written as a literal. R6's literal
    # 1787000000 predated its own fixture's notBefore by 585924 seconds and
    # the positive control failed with "certificate is not yet valid".
    notes = {
        "synthetic_validation_time": fixture["validation_time"],
        "synthetic_validation_time_source":
            "derived from the moment the fixture certificates were issued",
    }

    vhn_leaf = os.path.join(CERTS,
                            "vhn_leaf_from_sealed_p7s_parse_evidence.pem")
    vhn_ca = os.path.join(CERTS, "vhn_intermediate_selected_manual_pem.pem")
    vhn_root = os.path.join(CERTS, "vhn_root.pem")

    signature = mutation_fixtures.signature_mutation(
        vhn_leaf,
        os.path.join(CONTROLS, "vhn_leaf_der_signature_mutated.pem"),
        vhn_root, CONTROLS, intermediates_pem=vhn_ca)

    refusal = mutation_fixtures.parse_refusal(
        vhn_leaf,
        os.path.join(CONTROLS, "vhn_leaf_unparseable_der.pem"),
        CONTROLS)

    content = mutation_fixtures.content_mutation(
        os.path.join(ROOT, "references", "REF-11-vhn-covered-content.xml"),
        os.path.join(CONTROLS, "vhn_covered_content_one_byte_mutated.xml"),
        offset=0)

    # The synthetic positive control's own facts, measured rather than assumed.
    leaf_facts = run([policy.EXECUTABLES["openssl"], "x509", "-in",
                      fixture["leaf_pem"], "-noout", "-dates", "-ext",
                      "extendedKeyUsage,keyUsage"], SYNTHETIC)

    return {
        "synthetic": {
            "dir": os.path.relpath(SYNTHETIC, ROOT),
            "root_pem": os.path.relpath(fixture["root_pem"], ROOT),
            "root_der": os.path.relpath(fixture["root_der"], ROOT),
            "other_root_pem": os.path.relpath(fixture["other_root_pem"], ROOT),
            "intermediate_pem": os.path.relpath(fixture["intermediate_pem"],
                                                ROOT),
            "leaf_pem": os.path.relpath(fixture["leaf_pem"], ROOT),
            "content": os.path.relpath(fixture["content"], ROOT),
            "wrong_content": os.path.relpath(fixture["wrong_content"], ROOT),
            "content_mutated": os.path.relpath(fixture["content_mutated"],
                                               ROOT),
            "cms_detached": os.path.relpath(fixture["cms_detached"], ROOT),
            "leaf_facts": leaf_facts.stdout.decode("utf-8", "replace"),
            "sha256": {
                key: hashing.sha256_file(fixture[key])
                for key in ("root_pem", "intermediate_pem", "leaf_pem",
                            "content", "wrong_content", "cms_detached")
            },
        },
        "mutations": {
            "cert_signature": signature,
            "cert_parse_refusal": refusal,
            "content": content,
        },
        "notes": notes,
    }


def stage_anchor_from_der():
    """Stage REF-08's DER root as an exclusive PEM copy for `-CAfile`.

    `-CAfile` reads PEM. R4 handed it DER and the failure surfaced as a
    certificate error rather than an encoding error, which is why
    `operation_catalog._pem_anchor` now refuses DER by inspecting the first
    bytes rather than trusting the extension.

    The reference is not converted in place and is not touched: the staged
    copy is written under work/, read-only, and every identity field --
    subject, issuer, public key, fingerprint -- is proved equal between the
    source and the copy before the record is written. The source digest is
    re-measured after staging as well, because a conversion that altered its
    own input would otherwise be invisible.

    In R7 this was done once, outside any build script, and the staged anchor
    survived only in `work/`. R8 does not copy R7's `work/`, so the step
    belongs here, where it is repeatable and recorded.
    """
    path_policy.ensure_dir(STAGED_ANCHORS)
    dest = os.path.join(STAGED_ANCHORS, "vhn_root_from_der.pem")
    if os.path.exists(dest):
        return {"staged": False, "reason": "ALREADY_STAGED",
                "staged_pem_sha256": hashing.sha256_file(dest)}
    source = os.path.join(ROOT, "references", "REF-08-safe-root-ca-2017.der")
    record = trust_material.stage_der_anchor_as_pem(
        source, dest,
        expected_sha256=("1abddfa573cf1dcd5a75f164bc828e6d4177c4488495"
                         "35912eed3c7825bfc9fc"),
        audit_id="L1-A34", run_phase="RUN-A")
    trust_material.write_staging_evidence(
        record, os.path.join(STAGED_ANCHORS, "STAGING_EVIDENCE.json"))
    return {"staged": True,
            "source_der_sha256": record["source_der_sha256"],
            "source_reference_unchanged": record["source_reference_unchanged"],
            "identity_equal": record["identity_equal"],
            "staged_pem_sha256": record["staged_pem_sha256"],
            "staged_pem_path": record["staged_pem_path"]}


def main():
    for directory in (PREPARATION, CERTS, CONTROLS, SYNTHETIC, STAGED_ANCHORS):
        path_policy.ensure_dir(directory)

    intake = take_in_official_material()
    carried = carry_forward()
    official = cross_check_official()
    controls = build_controls()

    disagreements = [r for r in official if r.get("result") != "EQUAL"]

    anchor = stage_anchor_from_der()

    record = {
        "schema": "wpno.level1.l1a31-staging/1",
        "revision": "R8",
        "preparation_dir": os.path.relpath(PREPARATION, ROOT),
        "staged_anchor": anchor,
        "operator_intake_official_chain_material": intake,
        "carried_forward_from_r6": carried,
        "official_material_cross_check": official,
        "official_material_disagreements": disagreements,
        "controls": controls,
        "openssl": subprocess.run(  # noqa: S603
            [policy.EXECUTABLES["openssl"], "version"], shell=False,
            capture_output=True, timeout=30, env=policy.base_environment(),
            cwd=ROOT, check=False).stdout.decode("utf-8").strip(),
    }
    out = os.path.join(PREPARATION, "STAGING_RECORD.json")
    with open(path_policy.assert_writable(out), "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=2, sort_keys=True)
        fh.write("\n")

    print(json.dumps({
        "staging_record": os.path.relpath(out, ROOT),
        "staging_record_sha256": hashing.sha256_file(out),
        "certificates_carried": len(carried),
        "official_material_intake": intake["intake_directory"],
        "official_material_members": len(intake["members"]),
        "trusted_list_matches_its_published_digest":
            intake["trusted_list_self_check"].get("matches"),
        "official_cross_check": {r["staged"]: r["result"] for r in official},
        "official_disagreements": len(disagreements),
        "cert_signature_mutation_proven": controls["mutations"]
            ["cert_signature"]["proven_signature_fails"],
        "cert_parse_refusal_proven": controls["mutations"]
            ["cert_parse_refusal"]["proven_unparseable"],
        "content_mutation_digest_differs": controls["mutations"]["content"]
            ["digest_differs"],
        "synthetic_validation_time": controls["notes"]
            ["synthetic_validation_time"],
        "staged_anchor": anchor,
    }, indent=2, sort_keys=True))
    return 0 if not disagreements else 1


if __name__ == "__main__":
    sys.exit(main())
