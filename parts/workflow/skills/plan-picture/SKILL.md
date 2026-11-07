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

Read the plan's goal and its Behaviour. Name the one shift the picture must
carry, from this list:

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

Put it in the plan under the title and goal, before the phases, in a
`## Picture` section:

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

Rules:

- Inside a fenced block with no language tag, at most 76 columns, no tabs.
- One character set: plain `+ - | \` / > <` or box-drawing `┌ ─ ┐ │ └ ┘ ├ ┤ ▶`,
  never both in one picture.
- Labels are words from the plan: the same names its phases use. A name
  that only exists in the picture is a sign the picture drew something the
  plan does not build.
- Few labels. If the picture needs a legend, it does too much.
- The sentence under it is prose, outside the fence. It is what a screen
  reader gets, and what a reader who skips the art gets.

## 3. When it does not fit: an SVG page

Move to an SVG when the picture needs more than about eight boxes or lines
that cross. First ask whether the plan is too big for one session: a plan
that needs a big picture often wants to become a programme. Say so to the
person, rather than only drawing a bigger image.

When the SVG stays:

1. Write it next to the plan, `<plan-file-stem>.svg` (numbered
   `-1.svg`, `-2.svg` when there are several). Never overwrite an existing
   picture the plan does not own.
2. Draw it with the `artifact-diagramming` skill's inline-SVG rules when
   that skill is present: text as text, colours that hold in light and dark,
   a `<title>` and `<desc>`. Same anchor, same actor, same labels as step 1.
3. The plan's `## Picture` keeps a small ASCII outline (the main path, three
   to five boxes) and links the SVG:
   `Full picture: [<stem>.svg](<stem>.svg)`. The plan stays readable in a
   terminal without opening anything.
4. Open the page for the person before asking them anything about the plan:
   `amont-agent open '<path-or-url>'`. Without amont-agent, give the
   person the path in the final message and say it was not opened.

An HTML page instead of an SVG only when the picture needs interaction:
stepping through a programme's phases, a ticket that opens its detail.

## 4. Check it

Run the checker on the plan file:

```bash
python3 <this-skill-dir>/check.py <plan.md>
```

It fails (exit 1) on: no `## Picture` section, no fenced block in it, a
line over 76 columns, a tab, ASCII and box-drawing corners mixed, no
sentence after the block, and a linked `.svg`/`.html` that does not exist.
Exit 2 is a usage error, never a pass.

Then read the picture against this list. Redraw when one holds:

- the actor is missing, or nothing moves;
- it shows the whole system rather than the shift;
- a box or label is not in the plan;
- it is crowded: fewer boxes, more white space;
- it reads as a slide (title banner, bullet boxes, decorative frames).

Done when the checker exits 0 and none of the list holds.

## 5. Hand over

The picture is part of the plan: `/plan-review` reviews it with the rest,
and a reviewer may flag a picture that disagrees with the phases. A
change the person asks for that changes the mechanism redraws the picture
in the same delta.

A programme map has one picture of the path to its end state, redrawn
when a ticket changes that end state. Tickets get no picture of their own;
the plan written for a ticket does.

A plan that changes no mechanism (a version bump, a text fix) gets no
picture: write `## Picture` with one line, `none: <why>`, and the checker
accepts it.
