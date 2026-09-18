from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parent.parent
BEA_PREDICATES = (
    "-iname", "bea", "-o", "-iname", "bea[![:alnum:]]*", "-o",
    "-iname", "*[![:alnum:]]bea", "-o", "-iname",
    "*[![:alnum:]]bea[![:alnum:]]*",
)


def _find(root, predicates):
    result = subprocess.run(
        ["find", str(root), "-type", "f", "!", "-name", "._*",
         "(", *predicates, ")", "-print"],
        check=True, text=True, capture_output=True,
    )
    return {Path(line).name for line in result.stdout.splitlines()}


def test_bea_token_search_excludes_bearbeitung(tmp_path):
    expected = {"beA Export.pdf", "beA-export.pdf", "export_beA.pdf", "beA"}
    rejected = {"Bearbeitung.pdf", "algebra.pdf", "seabea.pdf"}
    for name in expected | rejected:
        (tmp_path / name).touch()

    assert _find(tmp_path, BEA_PREDICATES) == expected


def test_trackc_groups_shared_find_constraints():
    source = (ROOT / "TrackC_bestand.sh").read_text()
    assert 'find "$D" -type f ! -name "._*" \\( "$@" \\)' in source


def test_trackc_uses_bounded_bea_token_predicates():
    source = (ROOT / "TrackC_bestand.sh").read_text()
    assert '-iname "*bea*"' not in source
    for token in ("bea", "bea[![:alnum:]]*", "*[![:alnum:]]bea",
                  "*[![:alnum:]]bea[![:alnum:]]*"):
        assert f'-iname "{token}"' in source


def test_s7_groups_every_find_disjunction():
    source = (ROOT / "S7_bestand.sh").read_text()
    lines = [line for line in source.splitlines()
             if line.lstrip().startswith("find ") and " -o " in line]
    assert len(lines) == 3
    assert all("\\(" in line and "\\)" in line for line in lines)


def test_grouping_applies_type_and_appledouble_rules_to_every_branch(tmp_path):
    (tmp_path / "valid.p7s").touch()
    (tmp_path / "valid.sig").touch()
    (tmp_path / "._hidden.sig").touch()
    (tmp_path / "directory.sig").mkdir()
    predicates = ("-iname", "*.p7s", "-o", "-iname", "*.sig")

    assert _find(tmp_path, predicates) == {"valid.p7s", "valid.sig"}
