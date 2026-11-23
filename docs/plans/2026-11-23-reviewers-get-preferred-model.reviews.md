# Reviewers get their preferred model — full reviews

- architect (opus): R1 approve-with-changes, 3 findings (relais-review pin → person chose inherit; guard/process crate split; lookup precedence), 30k, 38 s. R2 approve, 36k, 12 s.
- backend (opus): R1 approve-with-changes, 5 findings (Task matcher, relais doc, counts, file names, failing check), 44k, 74 s. R2 approve-with-changes (#6 plugin dirs, applied), 52k, 23 s; re-runs approve 54k/13 s, 59k/20 s.
- lang:rust (opus): R1 approve-with-changes, 4 findings (backtester Bash-only, Task matcher, crate split, line parse), 35k, 63 s. R2 approve; #5 low carried: describe `backtest.rs` as registration only. 41k, 12 s.
- po (opus): R1 approve-with-changes, 4 findings (after-release measures; skip in Opus session — rejected: stale after /model, transcript parse per call; updatedInput reason; live relais-review check), 27k, 57 s. R2 approve, 32k, 13 s.
- tui (opus): R1 approve-with-changes, 3 findings (full message, Conflict branch, relaunch from message), 30k, 34 s. R2 approve; #4 low carried: describe the install `keep` line by its parts (real spacing differs). 35k, 11 s.
- unix (opus): R1 approve-with-changes, 4 findings (precedence, root from cwd, bounded read, marker normalisation), 35k, 55 s. R2 approve-with-changes (#1 plugin dirs, applied), 41k, 17 s.
- codex: approve-with-changes, 2 high applied: marker would break plan-apply `--record-fallback`; `relais install` needs `--user --write`.
