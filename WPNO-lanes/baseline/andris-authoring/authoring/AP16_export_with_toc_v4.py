#!/usr/bin/env python3
"""
AP-16 helper: opens a .docx in Microsoft Word (macOS), forces a full field
update (this recalculates the native TOC field, page-number fields, etc. —
same mechanism a human triggers with Cmd+A then F9 / "Felder aktualisieren"),
saves, and exports a PDF. Fully automates the one manual click a person
would otherwise need to do before sending.

Usage:
    python3 AP16_export_with_toc.py <document.docx> <output.pdf>
"""
import sys
import subprocess
import os

def update_fields_and_export_pdf(docx_abspath, pdf_abspath):
    script = f'''
    tell application "Microsoft Word"
        activate
        set theDoc to open file name POSIX file "{docx_abspath}"
        delay 1
    end tell
    tell application "System Events"
        tell process "Microsoft Word"
            keystroke "a" using command down
            delay 0.5
            key code 101
            delay 1.5
            -- Word's "updateFields" setting silently updates the TOC once on
            -- open; our F9 here is a second update, so Word always asks
            -- which mode to use. Select "Ganzes Verzeichnis aktualisieren"
            -- (second radio) and confirm.
            key code 125
            delay 0.3
            key code 36
            delay 1
        end tell
    end tell
    tell application "Microsoft Word"
        save theDoc
        save as theDoc file name "{pdf_abspath}" file format format PDF
    end tell
    delay 1
    tell application "Microsoft Word"
        try
            close active document saving no
        on error
            try
                close document 1 saving no
            end try
        end try
    end tell
    '''
    result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
    return result

def main():
    if len(sys.argv) != 3:
        print("Usage: python3 AP16_export_with_toc.py <document.docx> <output.pdf>")
        sys.exit(1)
    docx_path = os.path.abspath(sys.argv[1])
    pdf_path = os.path.abspath(sys.argv[2])

    result = update_fields_and_export_pdf(docx_path, pdf_path)
    if result.returncode != 0:
        print("FEHLER beim Aktualisieren/Export:")
        print(result.stderr)
        sys.exit(1)

    print(f"OK: Felder aktualisiert, PDF exportiert nach {pdf_path}")

if __name__ == '__main__':
    main()
