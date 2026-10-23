# 03 — Educational Content System

Content is part of the product. This section defines the lesson format, how content moves from authoring into the database, the editorial quality bar, and the initial library.

## 3.1 Content pipeline

```
content/**/*.yaml  ──(PR + editorial checklist)──►  main branch
        │
        ▼
`curiosity content validate`  (CI: schema + rules, no DB)
        │
        ▼
`curiosity content import`    (release step: idempotent upsert into Postgres)
        │
        ▼
lessons / lesson_versions / questions / answer_options / sources  (runtime copy, read-only to the app)
```

- **Source of truth is the repo** (D-5). The database holds the published runtime copy. No content is edited directly in the database.
- Git history serves as the editorial audit trail. Each lesson file carries `version`, `status`, `last_reviewed_on`, and `reviewers`.
- `content validate` runs in CI on every change. `content import` runs at deploy time after migrations (see [13](13-operations.md)).

### Import rules (`curiosity content import`)
1. Parse and validate every file (§3.3). If any file fails, the whole import aborts with no partial writes, in a single transaction.
2. Upsert `subjects`, `topics`, `sources` by `slug`/`key`.
3. For each lesson, compute `content_hash` = SHA-256 of the canonicalised lesson payload, excluding `status`, `position`, editorial metadata (`last_reviewed_on`, `reviewers`, `changelog`) and lesson-level relations (`related`, `prerequisites`). Editorial metadata is updated in place on the version row. This lets a reviewed draft be published without a version bump (15 §15.6, DEV-7).
   - No `lesson_versions` row with this `version` → insert a new version with its questions and options. If `status: published`, set `lessons.current_version_id` to it.
   - A row exists with the same `version` and the **same** hash → no-op.
   - A row exists with the same `version` but a **different** hash → **fail**: "content changed without a version bump". This is enforced for published versions. Draft versions MAY be overwritten in non-production environments (`CONTENT_ALLOW_DRAFT_OVERWRITE=true`).
4. `status: retired` → the lesson is hidden from discovery and new attempts. Existing review states continue to work (see [07 §7.3](07-learning-engine.md#73-spaced-repetition-scheduler-sm2-curiosity-v1)), and recall questions come from the last published version.
5. Lesson relations are rewritten from the files on every import.
6. The import prints a summary (created / unchanged / new versions / retired) and exits non-zero on any failure.

### Question identity across versions
- Questions and options have author-assigned `key`s that stay stable within a lesson (e.g. `check-anchor-1`, option keys `a`–`f`).
- A new lesson version creates new `questions` rows (new UUIDs) that keep the same `key`. History rows point at the exact version's question ID, so the data stays accurate even after a question is corrected.
- If a correction **changes which option is correct**, the editor MUST also change the question `key`. The analysis then treats the corrected item as a different item.

## 3.2 Lesson schema

Authoring format: one YAML file per lesson at `content/<subject>/<topic>/<slug>.yaml`. Long text fields use the Markdown subset defined in FR-LRN-2. Media live in `content/media/<slug>/` and are referenced by file name.

| Field | Type | Rules |
|---|---|---|
| `id` | UUID | Generated once by `curiosity content new`. Never changes. |
| `slug` | string | `^[a-z0-9]+(-[a-z0-9]+)*$`, ≤ 60 chars, unique, never reused after retirement. |
| `version` | int ≥ 1 | Bumped on every content change after first publication. |
| `status` | `draft` \| `published` \| `retired` | Only `published` is visible to users. |
| `subject` | slug | Must exist in `content/subjects.yaml`. |
| `topic` | slug | Must exist under the subject. |
| `position` | int | Curated order within the topic. |
| `title` | string ≤ 60 | Sentence case. |
| `description` | string ≤ 140 | One line, shown on cards. |
| `learning_objective` | string ≤ 200 | Starts with an observable verb ("Recognize…", "Explain…", "Distinguish…"). |
| `estimated_minutes` | int 3–10 | |
| `evidence_status` | `established` \| `mixed` \| `contested` | Overall status of the central claim. |
| `last_reviewed_on` | date | Required when `status: published`. |
| `reviewers` | list of strings | ≥ 1 for published: an author, plus a reviewer who is not the author. |
| `prerequisites` | list of slugs | Optional. Used for recommendation ordering. |
| `related` | list of slugs | 1–4. The first entry is the default "Next" lesson. |
| `sources` | list of `{key, note?}` | ≥ 2 for published, at least 1 of which is peer-reviewed or primary. Keys refer to `content/sources.yaml`. |
| `steps` | list of steps | See below. |
| `questions` | list of questions | See below. |

**Step types**

| `type` | Fields | Rules |
|---|---|---|
| `hook` | `body`, `image?` | Exactly 1, must be first. A question or real-world situation. ≤ 80 words. |
| `explanation` | `title?`, `body`, `image?` | 1–3. Each ≤ 220 words. Must cover the **mechanism** (why it happens). |
| `example` | `title?`, `body`, `kind: illustrative \| research`, `source_key?` | 1–3. `research` requires `source_key`. Illustrative examples MUST NOT be written as real studies. |
| `misconception` | `myth`, `correction` | ≥ 1. |
| `evidence` | `status: established \| debated`, `body`, `source_keys` | Required when `evidence_status` ≠ `established`. |
| `question` | `question_key` | References a `role: lesson` question. 2–4 per lesson, each appearing exactly once. |
| `summary` | `points` (2–4 strings, each ≤ 25 words) | Exactly 1, must be last. |

`image` = `{file, alt, caption?}`. `alt` is required and must be ≤ 200 chars. The file must be WebP or PNG, ≤ 300 KB, and supplied at 2× resolution.

**Question fields**

| Field | Rules |
|---|---|
| `key` | Unique within lesson. `^[a-z0-9-]+$`. |
| `role` | `lesson` (used in the player) or `recall` (used only in reviews). |
| `type` | `single_choice` (exactly 1 correct, 3–5 options), `multi_select` (≥ 2 correct, 4–6 options, all-or-nothing scoring), `true_false` (exactly 2 options keyed `true`/`false`). `estimate` (D-18): no options; an `estimate` block `{min, max, step, unit, answer, tolerance, anchor?}`; correct when the value is within `tolerance` of `answer`; lesson role only. |
| `prompt` | ≤ 300 chars. Scenario prompts are encouraged. |
| `options[]` | `{key, text ≤ 160, correct: bool, feedback ≤ 280}`. Every option needs feedback explaining why it is right or wrong. |
| `explanation` | ≤ 400 chars. A general explanation shown after any answer. |
| `shuffle` | bool, default `true`. Set to `false` for ordered options such as "All of the above" (discouraged). |

**Per-lesson question rules**
- 2–4 `lesson` questions. At least 1 must apply the concept to a new situation (not just recall the definition).
- **≥ 4 `recall` questions** (target 5–6). At most 1 may be definitional. The rest must be scenario or application questions, and at least 1 must ask the learner to *distinguish* the concept from a confusable neighbour (e.g. anchoring vs availability).
- Recall questions MUST NOT duplicate lesson questions or reuse their scenarios.
- No "all/none of the above" in recall questions. Distractors must be plausible misconceptions, not obviously silly.
- `true_false` is limited to 1 per role per lesson, because guessing is 50% likely to succeed.

## 3.3 Validation (`curiosity content validate`)

The validation is implemented as Pydantic models in `apps/api/app/content/schema.py`. The same models are used by the importer. The command fails on:
- schema violations, length limits, or unknown fields (`extra="forbid"`);
- broken references (topic, related, prerequisite, source keys, question keys, image files);
- step ordering rules, question-count rules, correct-option-count rules;
- duplicate slugs, IDs, or question/option keys;
- `published` lessons missing `last_reviewed_on`, `reviewers`, or sources;
- prerequisite cycles;
- media over the size limit or missing alt text.

Warnings (non-blocking, printed): `last_reviewed_on` older than 12 months; a lesson with fewer than 5 recall questions; total reading words outside 350–1,100.

## 3.4 Sources registry

`content/sources.yaml` holds one entry per reference:

```yaml
- key: nickerson-1998
  type: journal_article      # journal_article | book | book_chapter | institutional | dataset | other
  citation: "Nickerson, R. S. (1998). Confirmation bias: A ubiquitous phenomenon in many guises. Review of General Psychology, 2(2), 175–220."
  doi: "10.1037/1089-2680.2.2.175"
  url: null
  peer_reviewed: true
```

- Citations use APA 7 style. DOI is preferred over URL. URLs must be stable (publisher, institutional, or archive pages, not blogs).
- Sources are shown to users in the lesson's Sources sheet. They are also passed to the AI as context, but only as titles and citations. Full texts are never sent.

## 3.5 Editorial quality checklist

Every lesson PR includes this checklist in its description (template at `.github/PULL_REQUEST_TEMPLATE/lesson.md`). The **author** and an independent **reviewer** both tick each item. A lesson cannot be published until every item is ticked. "N/A" is allowed with a reason.

**Factual accuracy**
- [ ] Every empirical claim is supported by a listed source that the author has actually read (at least the abstract and relevant section).
- [ ] Numbers (effect sizes, percentages, sample sizes) appear only if they come directly from a cited source, and the source is cited next to them.
- [ ] Famous studies are described accurately (design, population, what was actually measured), without the popular embellishments.

**Reliability of sources**
- [ ] At least 2 sources, at least 1 of them peer-reviewed or primary.
- [ ] Review articles or meta-analyses are preferred over single studies where they exist.
- [ ] Replication status has been checked. If key findings failed to replicate or are disputed, the lesson says so in an `evidence` step.
- [ ] No sources from content farms, unsourced blogs, or AI-generated summaries.

**Clarity and readability**
- [ ] Plain language. Technical terms are defined at first use.
- [ ] Each explanation step makes one point. Sentences are mostly ≤ 25 words.
- [ ] The opening hook can be understood without prior knowledge.

**Conceptual depth**
- [ ] The lesson explains the mechanism (why it happens), not just the definition.
- [ ] It covers when the bias does *not* apply, or when the heuristic is actually useful.
- [ ] It names at least one practical implication or mitigation, and does not over-claim how well debiasing works.

**Quality of examples**
- [ ] Examples are realistic, varied (not all about money), and culturally broad.
- [ ] Illustrative examples are not presented as research findings.
- [ ] No examples that stereotype groups or trivialise mental-health conditions.

**Questions and feedback**
- [ ] Every question has exactly the right number of correct options, and the correct answer is unambiguous to a domain expert.
- [ ] Each option's feedback explains *why*, not just "Correct!" or "Wrong."
- [ ] Recall questions assess understanding through application or distinction, and do not repeat the lesson's wording.
- [ ] Distractors reflect real misconceptions.

**Avoiding misleading simplifications**
- [ ] No claim that a bias is "always" present or that everyone is equally affected.
- [ ] Contested framings (e.g. strict System 1 / System 2 dichotomies, the size of loss aversion, the Dunning–Kruger "Mount Stupid" curve) are presented as debated.
- [ ] Established findings, contested interpretations, and illustrative examples are visibly distinguished (evidence step, example `kind`).

**Final**
- [ ] `content validate` passes. The lesson has been read end-to-end in the app on a phone in both themes.
- [ ] `last_reviewed_on` is set to today. `reviewers` lists the author and the reviewer.

### Correction process
1. **Intake:** in-app reports (`content_feedback`), emails, or editorial re-review. Reports are triaged weekly via `curiosity content feedback list`.
2. **Severity:** *S1* = factual error or wrong answer key (fix within 2 working days, or retire the question/lesson immediately via a `retired` status or by removing the question in a new version). *S2* = misleading simplification or unclear wording (next content release). *S3* = typo or style (batch).
3. **Fix:** a new `version` with a changelog line in the file (`changelog: [{version, date, summary}]`). If the answer key changes, the question key changes too (§3.1).
4. **Close:** mark the feedback as resolved with a reference to the commit (`curiosity content feedback resolve <id> --note`).
5. **Scheduled re-review:** every published lesson is re-reviewed at least every 12 months. The CI warning in §3.3 surfaces lessons that are due.

## 3.6 Initial library

Subject: `psychology` (title "Psychology & Human Behavior"). Four topics, 27 lessons. **Launch gate: ≥ 20 published lessons**, covering every topic with at least 4 lessons each. The sources listed are *candidate* references from the spec author's knowledge. Each one MUST be verified by the editor before use (R-2).

Interest → topic mapping for onboarding: *Thinking clearly* → `foundations`, `judgment`; *Decisions & money* → `decisions`; *People & society* → `social`.

### Topic `foundations` — How judgment works
| # | slug | Title | Objective (abridged) | Evidence | Candidate sources |
|---|---|---|---|---|---|
| 1 | `what-is-a-cognitive-bias` | What is a cognitive bias? | Distinguish heuristics, biases, and errors; explain why shortcuts are often useful | established | Tversky & Kahneman 1974 (Science 185) |
| 2 | `fast-and-slow-thinking` | Fast and slow thinking | Explain dual-process accounts and their limits | mixed | Kahneman 2011 (book); Evans & Stanovich 2013 (Perspect. Psychol. Sci. 8(3)) |
| 3 | `regression-to-the-mean` | Regression to the mean | Recognize when extreme results naturally move toward average | established | Kahneman & Tversky 1973 (Psychol. Rev. 80(4)) |
| 4 | `survivorship-bias` | Survivorship bias | Spot conclusions drawn only from what "survived" a selection process | established | Mangel & Samaniego 1984 (JASA 79) |

### Topic `judgment` — Judging under uncertainty
| # | slug | Title | Evidence | Candidate sources |
|---|---|---|---|---|
| 5 | `availability-heuristic` | Availability heuristic | established | Tversky & Kahneman 1973 (Cogn. Psychol. 5(2)) |
| 6 | `representativeness-heuristic` | Representativeness heuristic | established | Kahneman & Tversky 1972 (Cogn. Psychol. 3(3)) |
| 7 | `base-rate-neglect` | Base-rate neglect | established | Bar-Hillel 1980 (Acta Psychol. 44(3)) |
| 8 | `conjunction-fallacy` | The conjunction fallacy | mixed | Tversky & Kahneman 1983 (Psychol. Rev. 90(4)); Hertwig & Gigerenzer 1999 (JBDM 12(4)) |
| 9 | `gamblers-fallacy` | The gambler's fallacy | established | Tversky & Kahneman 1971 (Psychol. Bull. 76(2)) |
| 10 | `anchoring` | Anchoring | established | Tversky & Kahneman 1974; Furnham & Boo 2011 (J. Socio-Econ. 40(1)) |
| 11 | `overconfidence` | Overconfidence | established | Moore & Healy 2008 (Psychol. Rev. 115(2)) |
| 12 | `hindsight-bias` | Hindsight bias | established | Fischhoff 1975 (JEP:HPP 1(3)); Roese & Vohs 2012 (Perspect. Psychol. Sci. 7(5)) |
| 13 | `dunning-kruger-effect` | The Dunning–Kruger effect | contested | Kruger & Dunning 1999 (JPSP 77(6)); Gignac & Zajenkowski 2020 (Intelligence 80) |

### Topic `decisions` — Choices, value and time
| # | slug | Title | Evidence | Candidate sources |
|---|---|---|---|---|
| 14 | `loss-aversion` | Loss aversion | mixed | Kahneman & Tversky 1979 (Econometrica 47(2)); Gal & Rucker 2018 (J. Consum. Psychol. 28(3)) |
| 15 | `framing-effect` | The framing effect | established | Tversky & Kahneman 1981 (Science 211) |
| 16 | `sunk-cost-fallacy` | The sunk cost fallacy | established | Arkes & Blumer 1985 (OBHDP 35(1)) |
| 17 | `endowment-effect` | The endowment effect | mixed | Kahneman, Knetsch & Thaler 1990 (JPE 98(6)) |
| 18 | `status-quo-bias` | Status quo bias | established | Samuelson & Zeckhauser 1988 (J. Risk Uncertain. 1(1)) |
| 19 | `present-bias` | Present bias | established | Laibson 1997 (QJE 112(2)); Frederick, Loewenstein & O'Donoghue 2002 (JEL 40(2)) |
| 20 | `planning-fallacy` | The planning fallacy | established | Buehler, Griffin & Ross 1994 (JPSP 67(3)) |

### Topic `social` — Beliefs and other people
| # | slug | Title | Evidence | Candidate sources |
|---|---|---|---|---|
| 21 | `confirmation-bias` | Confirmation bias | established | Nickerson 1998 (Rev. Gen. Psychol. 2(2)); Wason 1960 (QJEP 12(3)) |
| 22 | `motivated-reasoning` | Motivated reasoning | established | Kunda 1990 (Psychol. Bull. 108(3)) |
| 23 | `fundamental-attribution-error` | Fundamental attribution error | mixed | Ross 1977 (Adv. Exp. Soc. Psychol. 10); Gilbert & Malone 1995 (Psychol. Bull. 117(1)) |
| 24 | `halo-effect` | The halo effect | established | Nisbett & Wilson 1977 (JPSP 35(4)) |
| 25 | `conformity` | Conformity and social proof | mixed | Asch 1956 (Psychol. Monogr. 70(9)) |
| 26 | `in-group-bias` | In-group bias | established | Tajfel et al. 1971 (Eur. J. Soc. Psychol. 1(2)) |
| 27 | `bias-blind-spot` | The bias blind spot | established | Pronin, Lin & Ross 2002 (PSPB 28(3)) |

Deliberately excluded because of replication problems or weak evidence: ego depletion, power posing, social priming effects, and "learning styles". They may appear later as part of a "Science that didn't hold up" topic (deferred).

**Content production dependency (R-1):** 27 lessons × (≈ 700 words + 2–4 lesson questions + 5–6 recall questions + illustrations). An AI assistant MAY be used to draft lessons, but each draft must go through the full checklist with sources read by a human. AI drafts are never published unreviewed.

## 3.7 Exemplar lesson (format reference)

This shows the shape of a lesson file. Its wording is a draft and still needs to pass the checklist.

```yaml
id: 0192a7c4-5b1e-7c2a-9d3f-1a2b3c4d5e6f
slug: confirmation-bias
version: 1
status: draft
subject: psychology
topic: social
position: 1
title: Confirmation bias
description: Why we notice evidence that fits what we already believe — and miss what doesn't.
learning_objective: Recognize confirmation bias in how people search for, interpret, and remember evidence, and name one way to counter it.
estimated_minutes: 6
evidence_status: established
last_reviewed_on: null
reviewers: []
prerequisites: [what-is-a-cognitive-bias]
related: [motivated-reasoning, bias-blind-spot]
sources:
  - key: nickerson-1998
  - key: wason-1960
  - key: lord-ross-lepper-1979
steps:
  - type: hook
    body: |
      You're sure your new coworker is unfriendly. Over the next week you notice
      every short reply and forget the time they helped you. Was your first
      impression right — or did it decide what you'd notice?
  - type: explanation
    title: The core idea
    body: |
      **Confirmation bias** is the tendency to search for, interpret, and remember
      information in ways that support what we already believe. It is not one
      mistake but a family of them: *which* evidence we look for, *how* we read
      ambiguous evidence, and *what* sticks in memory.
  - type: explanation
    title: Why it happens
    body: |
      Testing a belief by looking for cases that fit it feels natural and is
      cognitively cheap. Ambiguous information is easier to read in line with an
      existing expectation. And beliefs we care about carry emotional stakes, so
      disconfirming evidence gets more scrutiny than confirming evidence.
  - type: question
    question_key: check-search
  - type: example
    kind: research
    source_key: wason-1960
    title: The 2-4-6 task
    body: |
      In Wason's task, people were told the sequence 2-4-6 fits a hidden rule and
      could test their own sequences. Many tested only sequences that fit their
      guess (like 8-10-12) and rarely tried ones that would prove the guess wrong.
  - type: example
    kind: illustrative
    body: |
      A manager who believes remote work hurts productivity reads one report of a
      missed deadline as proof — and explains away three on-time deliveries as luck.
  - type: misconception
    myth: Confirmation bias only affects people who aren't very smart or educated.
    correction: |
      It shows up across levels of intelligence and expertise. Knowing about the
      bias does not by itself remove it.
  - type: question
    question_key: check-interpretation
  - type: explanation
    title: What helps
    body: |
      Ask "What would I expect to see if I were wrong?" and look for that. Seek out
      the strongest version of the opposing view. These habits reduce the bias in
      some settings, but none of them eliminates it.
  - type: summary
    points:
      - We tend to seek, interpret, and recall evidence in ways that fit our beliefs.
      - It affects search, interpretation, and memory — not just one step.
      - Deliberately looking for disconfirming evidence helps, but doesn't make us immune.
questions:
  - key: check-search
    role: lesson
    type: single_choice
    prompt: Priya thinks a supplement improves her sleep. Which test best avoids confirmation bias?
    options:
      - key: a
        text: Reading reviews from people who say it worked for them
        correct: false
        feedback: Testimonials from satisfied users are exactly the evidence that fits her belief.
      - key: b
        text: Tracking her sleep on nights with and without the supplement, without looking at the label
        correct: true
        feedback: Comparing both conditions — ideally blind — lets evidence against the belief show up.
      - key: c
        text: Noting the nights she slept well after taking it
        correct: false
        feedback: Counting only the hits ignores the misses and the nights without the supplement.
    explanation: Avoiding confirmation bias means looking for evidence that could show you're wrong, not only evidence that fits.
  - key: check-interpretation
    role: lesson
    type: true_false
    prompt: "True or false: confirmation bias is only about which information we search for."
    options:
      - {key: "true", text: "True", correct: false, feedback: "It also affects how we interpret ambiguous evidence and what we remember."}
      - {key: "false", text: "False", correct: true, feedback: "Right — search, interpretation, and memory are all affected."}
    explanation: The bias operates at several stages of handling evidence.
  - key: recall-jury
    role: recall
    type: single_choice
    prompt: After deciding early that a defendant is guilty, a juror sees an ambiguous alibi as "obviously made up." This is mainly an example of confirmation bias in…
    options:
      - {key: a, text: "searching for evidence", correct: false, feedback: "The alibi was presented to them — the bias here is in how it was read."}
      - {key: b, text: "interpreting evidence", correct: true, feedback: "Ambiguous evidence was read to fit the existing belief."}
      - {key: c, text: "remembering evidence", correct: false, feedback: "Nothing here depends on later recall."}
    explanation: The same evidence can look strong or weak depending on what we already believe.
  # … at least 3 more recall questions, including one distinguishing confirmation bias from the availability heuristic
```
