#!/usr/bin/env python3
"""
Helper: takes a clean AP-16/17 test docx and APPENDS a new paragraph
containing a fake IBAN + an unlisted/invented Az. into it, to prove the
AP-17 guardrail correctly BLOCKS a poisoned document. SYNTHETIC test only.

Appends a brand-new paragraph (instead of editing existing text) so it
works even after Word has re-saved the file and split text across
multiple runs, which breaks naive substring find-and-replace.

Usage: python3 AP17_make_poisoned_test.py <clean.docx> <poisoned.docx>
"""
import sys, zipfile, shutil, os, tempfile, subprocess, re

def main():
    clean_path = os.path.abspath(sys.argv[1])
    poisoned_path = os.path.abspath(sys.argv[2])
    tmpdir = tempfile.mkdtemp()
    subprocess.run(['unzip', '-q', clean_path, '-d', tmpdir], check=True)

    doc_xml_path = os.path.join(tmpdir, 'word', 'document.xml')
    with open(doc_xml_path, encoding='utf-8') as f:
        xml = f.read()

    poison_text = ('SYNTHETISCHER TESTZUSATZ (AP-17 Negativtest): Ueberweisung bitte auf '
                   'DE89370400440532013000 unter Az.: 99 X 999/99.')
    new_paragraph = f'<w:p><w:r><w:t xml:space="preserve">{poison_text}</w:t></w:r></w:p>'

    # Insert the new paragraph right before the final sectPr (end of body),
    # so it lands as the last real paragraph of the document.
    m = re.search(r'(<w:sectPr[ >])', xml)
    if not m:
        print("FEHLER: <w:sectPr> nicht gefunden, kann Testabsatz nicht einfuegen")
        sys.exit(1)
    insert_pos = m.start()
    xml = xml[:insert_pos] + new_paragraph + xml[insert_pos:]

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
