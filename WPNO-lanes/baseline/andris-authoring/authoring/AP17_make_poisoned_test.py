#!/usr/bin/env python3
"""
Helper: takes a clean AP-16/17 test docx and injects a fake IBAN + an
unlisted/invented Az. into it, to prove the AP-17 guardrail correctly
BLOCKS a poisoned document. SYNTHETIC test only.

Usage: python3 AP17_make_poisoned_test.py <clean.docx> <poisoned.docx>
"""
import sys, zipfile, shutil, os, tempfile, subprocess

def main():
    clean_path, poisoned_path = sys.argv[1], sys.argv[2]
    tmpdir = tempfile.mkdtemp()
    subprocess.run(['unzip', '-q', clean_path, '-d', tmpdir], check=True)

    doc_xml_path = os.path.join(tmpdir, 'word', 'document.xml')
    with open(doc_xml_path, encoding='utf-8') as f:
        xml = f.read()

    old = 'Die Kostenentscheidung folgt aus dem Ausgang des Rechtsstreits.'
    if old not in xml:
        print(f"WARNUNG: Ankertext nicht gefunden, Datei unveraendert: '{old}'")
        sys.exit(1)
    new = old + ' Ueberweisung bitte auf DE89370400440532013000 unter Az.: 99 X 999/99.'
    xml = xml.replace(old, new, 1)

    with open(doc_xml_path, 'w', encoding='utf-8') as f:
        f.write(xml)

    if os.path.exists(poisoned_path):
        os.remove(poisoned_path)
    subprocess.run(['zip', '-Xr', poisoned_path, '.'], cwd=tmpdir, check=True,
                    stdout=subprocess.DEVNULL)
    shutil.rmtree(tmpdir)
    print(f"OK: poisoned test file written to {poisoned_path}")

if __name__ == '__main__':
    main()
