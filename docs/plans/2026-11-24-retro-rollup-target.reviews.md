## Full reviews (reference)

- backend round 1 (opus, 27k, 35 s): approve-with-changes; 4 findings, all applied.
- backend round 2 (opus, 36k, 51 s): approve-with-changes; carried into implementation:
  1. require `.calls>0` in the jq filter (rate is null at 0 calls);
  2. reason text `no roll-up row for <rule> (no closed week, no tool, or an older greenbelay)`;
  3. drop "(greenbelay's journal keeps about two days)" from the old line 148;
  4. add a real-output check on a scratch journal (`tests/rollup_cli.rs` in greenbelay).
