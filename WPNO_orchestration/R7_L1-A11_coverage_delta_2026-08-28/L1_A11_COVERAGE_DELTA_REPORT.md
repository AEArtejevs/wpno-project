# L1-A11 official coverage delta report

## Outcome

The focused 2026-08-19 through 2026-08-27 coverage delta is closed. The saved official BGH annual page was generated at 2026-08-28 00:15:49 CEST (2026-08-27T22:15:49Z), after the end of 2026-08-27 in the source jurisdiction. It states that the individual Präsidium decisions for the 2026 Geschäftsverteilungsplan are listed on that annual page. Its latest listed decision is 2026-08-11, and it lists no decision in the delta interval. The page's current annual PDF download is byte-identical to the previously accepted PDF. Together, these facts establish that the unchanged PDF remained the current complete published 2026 set through the required date.

REF-05 is ACCEPTED, L1-A11 is READY, and authoritative planning readiness is 34/35. The sole remaining gate is L1-A24 — human external launch-directory decision.

## Four-artifact verification

- `REF-05_SUPPLEMENT_MANIFEST.sha256`: valid when verified from its manifest directory; all three entries returned `OK`. Manifest SHA-256: `374e18e51923327a25ad7ad285ae708db9ea1b3d9845c085194ae813db2f0e23`.
- Symlinks: none among the four specified artifacts.
- Official saved page: regular UTF-8 HTML, 176,344 bytes, SHA-256 `e6dfe17c4dc185796c5d0d0114b2236967f8ff053275962b304db6e7f3035229`.
- Current PDF: regular PDF 1.7, 900,744 bytes, SHA-256 `da9f847e6532bfacfc6f3a8f55edba9c3ad5f346b2242f5918668c938e7b6d18`.
- Capture provenance: regular UTF-8 text, 2,030 bytes, SHA-256 `58631914cf3ceeec867d5caf9dc27000915245fc2af125a534b01f8a200dd8e1`.
- Official source host: `www.bundesgerichtshof.de` in the saved-from marker, canonical URL, page navigation, decision links, and current-PDF link.
- Capture time: the BGH page-generation marker is `Fri Aug 28 00:15:49 CEST 2026`, normalized to `2026-08-27T22:15:49Z`; this is after the end of 2026-08-27 in Germany (CEST).

## Saved-page identity and annual-set meaning

The substantive page is a genuine saved BGH page, not an operator-authored substitute. Evidence includes the official canonical URL, `Government Site Builder` generator metadata, BGH title/navigation/imprint structure, official annual breadcrumb and heading, BGH-hosted decision anchors, current-download link, and the BGH page-generation marker. Browser-extension-injected markup is present after the BGH page and was ignored.

Page title: `Der Bundesgerichtshof - Das Gericht : Geschäftsverteilungsplan 2026 : Präsidiumsbeschlüsse 2026`.

Page year: `2026`.

Annual-set representation: the page says, `Nachfolgend finden Sie die einzelnen Präsidiumsbeschlüsse zum Geschäftsverteilungsplan 2026.` This identifies the official annual page as the place where the individual 2026 decisions are listed. Therefore, its post-period capture can establish the complete/current published annual set; the conclusion does not rely on general web-search silence.

Listed decision dates, in page order:

1. 2026-08-11
2. 2026-07-07
3. 2026-06-17
4. 2026-04-28
5. 2026-02-24
6. 2026-01-27

Latest listed decision: `2026-08-11`. The page's latest displayed document line is `Karlsruhe, den 18. August 2026`, corresponding to that decision. No listed decision or amendment date falls within 2026-08-19 through 2026-08-27.

The page identifies this current annual PDF download: `https://www.bundesgerichtshof.de/SharedDocs/Downloads/DE/DasGericht/GeschaeftsvertPDF/2026/aenderungenGeschaeftsverteilung2026.html?nn=372306`, titled `Präsidiumsbeschlüsse zum Download`.

## PDF comparison and structural status

The current PDF hash exactly matches the prior expected SHA-256 `da9f847e6532bfacfc6f3a8f55edba9c3ad5f346b2242f5918668c938e7b6d18`. There is no new or different PDF material to inspect. Byte identity reuses the prior accepted structural validation: PDF 1.7, linearized structure, page objects, terminal `startxref` and `%%EOF`, and successfully inspected compressed content. A focused marker check also confirmed the terminal cross-reference pointer, balanced object/end-object markers, catalog/root/pages markers, and EOF. The original PDF inspection was not rerun.

## Narrow updates

Only the REF-05 coverage record, L1-A11 binding, all-35 readiness JSON/Markdown summary, reference manifest, changed-files manifest, and R7 build manifest were updated. No shared controller executable changed. No controller/package suite, other audit, full readiness measurement, pre-freeze verification, live audit, freeze, Git operation, or network action was run. The prior PARTIAL closure report and status remain unchanged as superseded coverage evidence.
