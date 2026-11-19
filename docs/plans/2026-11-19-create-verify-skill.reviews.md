# Full reviews: a generator skill writes each repo's verify skill


Round 1 (backend, python): both approve-with-changes. Backend: 1 blocking
(`adds=contract`), 2 high (grh pin unnamed; phase order cannot run: the
pilots precede the release and the F2 change), 2 medium (merge Phases 1 and
4; UI bullet), 2 low. Python: 1 high (no stdlib frontmatter parser), 2
medium (copy the right test; heading-line matches), 2 low. 34k/64 s and 39k/44 s.

Round 2 plus new seats: backend approve-with-changes (3: zero-baseline
rule, picture, grh line); python (F2 sentences untested; catalog test;
withdrew the check.sh claim); architect (1 high: evidence path conflicts
with F3; `run` skill does not exist; optional parts; Phase 4 has no
branch; no sign-in line); po (1 high: baseline unmeasurable from plans;
Phase 4 undated; duro-app history); tui (1 high; launch prompts; output
shapes; sign-in line); unix (2 high: kill mechanism, foreign-server
readiness; 3 medium: trap, exit codes, `ps` diff). 25k to 32k, 18 s to 63 s each.

Final round: backend, tui, po approve with lows carried; architect, unix
approve; python found 1 high (an EXIT trap tears the app down between tool
calls) which unix confirmed independently; applied, then all six re-ran as a
delta and approved. Carried into implementation: Phase 4 renamed "Dated
check"; Cleanup verifies the pidfile leader before signalling and prints
`ok:`/`fail:`; pidfile and log live in F3's directory; Doctor exit meanings
pinned in the test; 80-column lines and the log path on failure; a rollback
rule if a pilot run needs more repairs than its baseline; a run floor
before the 2026-12-19 date decides.
