# Skill: GitHub Triage Rubric

## Goal

Classify one GitHub issue or pull request into a consistent triage report:
a category, a priority, a short summary, suggested labels, and one concrete
next action. The same rubric is used for every item so reports are comparable
across runs.

## Categories

- `bug`: something that worked before is broken, an error, crash, wrong
  output, or a regression. Reports of incorrect behaviour belong here even
  when the reporter is unsure.
- `feature`: a request for new capability, a new option, an integration, or
  an enhancement to existing behaviour.
- `question`: the reporter is asking how something works, whether something
  is supported, or for guidance. No defect or new capability is claimed.
- `docs`: the problem or request is about documentation, examples, README,
  comments, or wording. A confusion caused purely by missing docs is `docs`,
  not `question`.
- `other`: anything that does not fit the four categories above, including
  maintenance chores, release tasks, and meta discussion.

## Priorities

- `critical`: data loss, security exposure, or a total outage of a core
  workflow with no workaround.
- `high`: a core workflow is broken or blocked for many users, or a PR that
  fixes such a break is waiting.
- `medium`: a real problem or valuable improvement with a workaround, or
  scope limited to some users.
- `low`: cosmetic issues, minor docs gaps, nice-to-have improvements.

When in doubt between two priorities, choose the lower one and say why in
the summary.

## Label vocabulary

Suggest labels only from this set: `bug`, `enhancement`, `question`,
`documentation`, `needs info`, `good first issue`, `help wanted`,
`duplicate`, `wontfix`. Always include the label that matches the category
(`bug`, `enhancement`, `question`, or `documentation`) when one exists.
Add `needs info` when the report lacks the detail needed to act.

## Next action

Name one concrete next step a maintainer can take, for example:
"Ask the reporter for a minimal reproduction", "Reproduce against the
latest release and confirm the regression", "Review the proposed change
and request tests", "Answer with a link to the relevant docs section and
close if resolved", "Split into a scoped implementation task".

## Guardrails

1. Judge only from the title, body, labels, and metadata provided. Do not
   invent facts about the codebase or the reporter.
2. Keep the summary to two or three sentences: what the item is, why it
   matters, and any blocker or missing information.
3. Never suggest a label outside the vocabulary above.
