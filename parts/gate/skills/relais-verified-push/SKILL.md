---
name: relais-verified-push
description: Verify a push actually left before trusting it — gate status, rehearsal, a bare push, then confirm the remote ref moved.
---

# /relais-verified-push

A push that "succeeded" is not the same claim as a push that left. Run
these four steps in order, from the repository the branch lives in.

## Steps

1. Check what pushing next gates: `amont list --json --stage pre-push
   --pushed`. The output is the `amont-list-v1` envelope: a `checks`
   array whose rows carry `id`, `effective_severity` and `status`. Read
   it before assuming the push is clean.

2. Rehearse the push gate on a snapshot of HEAD, ahead of time:
   `amont rehearse --wait`. This runs the same checks `git push` would
   run, with no remote connection open, so the push itself is fast and
   does not hold the remote idle while a suite runs.

3. Land the branch, bare, alone in its command, in the foreground:

   ```sh
   amont land --json
   ```

   It pushes the branch and reads the remote back. The push guards judge
   a land as they judge a `git push`, in that shape only; any other shape
   is held under deny. Where amont or amont-agent is missing, or
   `amont --version` is below 1.54 or `amont-agent --version` below 2.41
   (the guards would not see the land), push instead, bare:

   ```sh
   git push
   ```

   Never pipe `amont land` or `git push` into `tail`, `head` or `grep`. A
   pipeline's exit status is the LAST command's, so the trimming command
   reports exit 0 however the push actually ended, and the trimmed output
   discards the one line that would have said why it failed. If output
   must be trimmed, redirect to a file and read the file — never pipe a
   mutating command's own exit status away.

4. Confirm the ref actually moved, against the remote, not the local
   log. After `amont land`, exit 0 is that proof. Exit 4: the remote
   accepted the push but shows another sha, so read `remote_after` before
   anything else. Exit 1 is refused. Exit 3 is unreachable (nothing
   pushed) or unverified (the push was accepted but could not be read
   back): run the `git ls-remote` that land prints before landing again.
   After a `git push`:
   `git ls-remote origin refs/heads/<branch>`, and compare the sha it
   reports to `git log --oneline -1 <branch>`; only a match is a push
   that left.

## Rules

- Never trust a `git push` exit code alone; step 4 is the actual
  verification. `amont land` does step 4 itself, which is why its exit
  code can be trusted.
- A rehearsal failure is the push gate telling you now what `git push`
  would have refused later — fix it before step 3, not after.
