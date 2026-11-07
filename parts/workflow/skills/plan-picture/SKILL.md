---
name: plan-picture
description: Draw the one picture that explains what a plan or a programme builds — ASCII in the plan by default, an SVG page beside it when the picture does not fit. Use in plan mode before /plan-review, when a programme map is charted or its end state changes, and when asked to draw, sketch or illustrate a plan.
---

# plan-picture

A plan gets one picture, and the picture says what changes. The reader
should get the mechanism before reading the phases.

Method borrowed from ian-xiaohei-illustrations (helloianneo): draw only
where understanding shifts, one idea per image, an actor that does the work,
and a check after drawing. Its raster generation, its mascot and its
per-article metaphor stay out. A plan's picture has to show the real
mechanism, not a clever image.

## 1. Pick the anchor

Read the plan's goal and what it changes (its Behaviour and phases; for a
programme map, its end state and tickets). Name the one shift the picture
must carry:

| anchor | when | shape |
|---|---|---|
| before / after | the plan changes how something flows | two panes, `today` and `after this plan` |
| loop | the plan adds or closes a feedback loop | a cycle, with the new edge marked |
| branch | the plan adds a decision point | one path that forks, each arm labelled |
| breakpoint | the plan moves where something fails or stops | a path with the stop shown at its old and new place |
| path to an end state | a programme map | tickets as stations, `you are here` marked |

Then name the **actor**: the thing that moves through the picture (a push,
a request, a run, a ticket). The actor is what the arrows carry. A picture
with only static boxes is an architecture chart, not this.

Done when you can say in one sentence: "<actor> used to <X>, after this
plan it <Y>." That sentence goes under the picture.

## 2. Draw it in ASCII

Put it in a `## Picture` section placed after the H1 and its
`## Review panel` section (which plan-review keeps directly under the H1),
before the phases:

````markdown
## Picture

```
 today                        after this plan
 -----                        ---------------
 agent --push--> remote       agent --land--> [gates] --> remote
          \                                     |
           `--> CI is red                       `--red--> agent
                (too late)                           (before it leaves)
```

The gates move from after the push to before it, so a red tree never
reaches the remote.
````

Rules (the checker in step 4 enforces the ones marked ✓):

- ✓ One fenced block (backticks or tildes), with no language tag, at
  most 76 columns, no tabs.
- ✓ One character set: ASCII strokes (`-- -> | +-`) or box-drawing
  (`┌ ─ ┐ │ └ ┘ ├ ┤ ▶`), never both in one picture.
- ✓ A sentence of four words or more after the block, in prose outside
  the fence. It is what a screen reader gets, and what a reader who skips
  the art gets.
- Labels are words from the plan: the same names its phases use. A name
  that only exists in the picture is a sign the picture drew something the
  plan does not build.
- Few labels. If the picture needs a legend, it does too much.

## 3. When it does not fit: an SVG page

The SVG tier is for a picture that needs more than about eight boxes or
lines that cross. Before drawing one, judge for yourself whether the plan
is too big for one session: a plan that needs a big picture often wants to
become a programme. If you think it does, say so in the message that
presents the plan, after the page is open.

A programme map starts in this tier: its path to the end state outgrows
eight boxes as soon as it has a few tickets. Its `## Picture` still holds
one outline block, not one per ticket.

`<this-skill-dir>` below is where this file sits; installed by grh, that
is `~/.claude/skills/plan-picture`.

1. Name the SVG `<date>-<slug>.svg`: today's date (`YYYY-MM-DD`) and the
   plan's H1 in kebab-case, five words at most. Write it next to the plan.
   The plan links it by that bare name, so the link reads the same in plan
   mode and once landed beside the plan in `docs/plans/`, and landing does
   not change the reviewed body. If a file of that name already exists in
   either place, pick another slug before the panel runs; never overwrite
   it. A clash found only at landing means a rename, which changes the
   body: the backend reviewer re-runs on it.
2. Draw it with the `artifact-diagramming` skill's inline-SVG rules when
   that skill is present. Without it: text as `<text>`, not paths; a
   `<title>` and a `<desc>` holding the step 1 sentence; colours through
   `currentColor` or a `prefers-color-scheme` style, so it holds in light
   and dark. Same anchor, same actor, same labels as step 1.
3. The plan's `## Picture` keeps a small ASCII outline (the main path, three
   to five boxes), the sentence, and the link with the file's short hash:

   ```markdown
   The gates move before the push. Full picture: [the gates](2026-11-08-gates-before-push.svg) @3f9a1c2
   ```

   `python3 <this-skill-dir>/check.py --hash <file>.svg` prints the hash.
   It reads CRLF as LF, so a checkout's line endings do not stale it.
   The hash puts the SVG under the plan's reviewed body: a redraw changes
   the hash, so the plan changes and the panel sees it.
4. Open the page for the person before asking them anything about the plan:
   `amont-agent open '<path-or-url>'`. Without amont-agent, give the
   person the path in the final message and say it was not opened.

An HTML page instead of an SVG only when the picture needs interaction:
stepping through a programme's phases, a ticket that opens its detail.
The same naming, hash and opening rules apply.

## 4. Check it

```bash
python3 <this-skill-dir>/check.py <plan.md>
```

Exit 0: it holds. Exit 1: findings, one per line. Exit 2: usage or an
unreadable file, never a pass. Beyond the ✓ rules it fails on: no
`## Picture` section, an empty one, a fence never closed, a second block,
a linked `.svg`/`.html` that is missing, absolute, outside the plan's
directory, unhashed or whose hash is stale.

Then read the picture against this list. Redraw when one holds:

- the actor is missing, or nothing moves;
- it shows the whole system rather than the shift;
- a box or label is not in the plan;
- it is crowded: fewer boxes, more white space;
- it reads as a slide (title banner, bullet boxes, decorative frames).

Done when the checker exits 0 and none of the list holds.

## 5. Hand over

The picture is part of the plan: `/plan-review` runs the checker before
seating the panel, and the backend reviewer checks that the picture agrees
with the phases. A change the person asks for that changes the mechanism
redraws the picture in the same delta, with its new hash.

When the plan lands, worktree-task copies the SVG beside the landed plan
under the same name and runs the checker on the landed file.

A programme map has one picture of the path to its end state, redrawn
when a ticket changes that end state. Tickets get no picture of their own;
the plan written for a ticket does.

A plan that changes no mechanism (a version bump, a text fix) gets no
picture. Its `## Picture` holds one line, `none: <why>`, with a reason of
three words or more, and nothing else. The backend reviewer may challenge
the reason.
