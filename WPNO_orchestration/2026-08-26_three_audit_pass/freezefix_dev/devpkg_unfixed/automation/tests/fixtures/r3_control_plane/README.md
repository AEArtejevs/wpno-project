# R3 control plane, unmodified

Byte-identical copies of the frozen R3 controller modules and schemas,
taken from

    /Users/martinotten/WPNO/08.18.26_Level1_Audits_R3/automation/

They exist so that `test_r3_blocker_reproduction_fails_on_unmodified_R3_copy`
can demonstrate the original defect against the code that actually had
it, inside a scratch replica, without reading or writing R3 itself.

Nothing here is imported by the R4 controller. The R3 self-tests are not
included, so test discovery cannot collect a second copy of the suite.
Digests are in `R3_FIXTURE_MANIFEST.sha256`, relative to this directory.
