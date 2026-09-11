# BCP — Blueprint Completion Protocol

> **A development paradigm that lets domain experts build complex systems with AI, safely.**

[中文版](README.zh-CN.md) | **English**

BCP is not a tool, not a framework, not a product. It is a **coordination constitution** — it fixes what the human, the AI, and the symbolic system each do, what they must not do, and who has the final say.

Its core is one sentence:

**You set the direction, the AI executes, and something that is not an AI checks whether the AI lied.**

The three letters come from **Blueprint Completion**: the *blueprint* is the meta-approved design (phase B), *completion* is Yang filling an incomplete context into a complete artifact, and the *protocol* is the set of rules about who decides what.

> 📐 Full paradigm and mechanical contracts (three-party authority, R1–R8 rule table, ledger schema, evolution operators, applicability boundary, all design rationale) → **[Blueprint.md](Blueprint.md)**

## Why BCP

AI can already write code, run analysis, and generate plans. But once you **cannot review the AI's output line by line**, you face three problems:

1. **The AI silently did something you never asked for.** You asked for data cleaning; it "helpfully" added a deduplication step — and your domain knowledge tells you that dedup is wrong.
2. **The AI says it checked, and you don't believe it.** AI checking AI is a probabilistic system verifying a probabilistic system: the same blind spots, the same biases, the same hallucinations.
3. **Experience does not accumulate across sessions.** The pitfall you hit last week is hit again this week. The AI doesn't remember, and neither do you.

BCP answers with three mechanisms:

- **Declared collision** — the AI must declare what it did; the symbolic system mechanically checks the declaration against the facts.
- **Zero-LLM adjudication** — whatever checks the AI must itself not be an AI: a compiler, a test chain, a mechanical predicate. Same input, same output, always.
- **Failure archive + delayed verification** — failures are compressed into avoidance sentences, the meta's feedback is recorded late, and the system gets sharper with use.

## The three parties

BCP has exactly three roles:

| Role | Who | Does | Nature |
|---|---|---|---|
| **Meta** (元) | Human (domain expert) | States intent, approves designs, adjudicates evolution, feeds back real-world outcomes | The only party accountable for "is it good?" |
| **Yang** (阳) | LLM | Completes (完形): drafts plans, writes code, writes docs, given context | Probabilistic: the more complete the context, the more convergent the output |
| **Yin** (阴) | Symbolic system | Compiles, tests, collides mechanically, records the ledger | Deterministic: same input, same output, no position |

Three iron rules:

1. **The meta always holds final verification.** Yin's PASS is a ticket to entry, not a completion state. Whether the output is actually useful in reality can only be judged by the meta, later.
2. **Yin is always zero-LLM.** A probabilistic system cannot verify a probabilistic system.
3. **Yang cannot self-certify.** Any arrangement in which AI checks AI is cheating.

## The workflow

One-line chain: `intent →(meta)→ B design →(assembly)→ P plan →(Yang completes)→ C code →(Yin collides)→ consolidation`.

Four artifacts change phase along the chain: **B design** (solid, meta-approved) → **P plan** (gas, transient, consumed by the agent) → **C code** (solid, the only implementation fact) → **A rules** (liquid, settled back). Rules that are repeatedly recalled and validated may crystallize through a gate into **S skills** (solid).

> **Full workflow graph** (all nodes: failure archive, delayed-verification axis, sleep rhythm, consolidation and promotion/demotion) → **Blueprint §1.2** (single source; avoids drift from duplication).

## Five key mechanisms

### 1. check — mechanical collision

`bcp/check.py` is Yin's core tool. It does not judge "is the code good"; it checks whether the **seams between artifacts** line up:

- Does the design section cited by the plan actually exist? (R6 anchor resolution)
- Are the files the plan declares exactly the files in `git diff`? (R6 two-way collision)
- Do the plan's acceptance commands actually run green? (R6 accept execution)
- Do the paths written in documents actually exist? (R5 ghost paths)
- Does the produced skill match the structure contract? (R8 skill structure)

Every run appends to the ledger. PASS is a ticket to entry; FAIL comes with a repair direction.

### 2. ledger — the evidence stream

`bcp/ledger.jsonl` is an append-only evidence stream. Every collision, every rule injection, every failure archive appends a record.

The ledger answers two questions:

- **What happened historically** — which rules are violated often? Which skills were never recalled? Which domains were never injected?
- **What to do next** — `bcp/evolve.py` reads the ledger to produce candidates, sleep reads it to build the checklist, memory-gate reads it to decide injections.

The ledger never adjudicates. It supplies data; adjudication stays with the meta.

### 3. rules — the carriers of experience

Rules are written by the agent at task closeout, following the backflow protocol, into `.pi/rules/<domain>.md`:

- **Pitfall candidates** (≤3): written at task closeout.
- **Failure patterns** (one mandatory per FAIL): compressed to a title + avoidance sentence (≤200 chars), into the ledger and the rule file.
- **Rule page**: problem + root cause + evidence + avoidance sentence (10–30 lines), with a one-line table of contents at the top.

Rules flow into the A kernel **without a gate** — liquid self-corrects, bad rules get washed out by the evolution operators. Codifying a rule into `check` (making it a mechanical predicate) also needs **no meta approval** — the predicate is mechanically verifiable, so the evidence is the warrant. What *does* need meta approval (the gate) is **admitting a design into B** and **crystallizing a skill**.

### 4. skill — the crystallization product

A skill is decided jointly by **rules supplying content and the ledger supplying evidence**:

- Rules / raw trajectories supply reusable procedural knowledge.
- The ledger supplies recall counts, validation records, failure patterns.
- evolve section ⑦ collides both ways: a directory with no record = crystallization bypassing the gate; a record with no directory = ghost registration.
- **After meta approval**, the agent produces `deliverables/<name>/SKILL.md`, checked by the R8 structure gate.

The default artifact is a **text skill** (Markdown + frontmatter). Compiling to Python is an optional optimization (not implemented yet — see Blueprint §8.2, unwired candidates).

### 5. sleep — the metabolic rhythm

`sleep` turns inspection from "remember to do it" into "triggered by activity":

- **Trigger**: commits − last REPORT baseline > 30.
- **Execution**: mechanical reconciliation (evolve + selfcheck) → write a checklist → meta rules on each item → tick → delete the list → REPORT recorded.
- **Waking up** = a new evolve REPORT lands in the ledger; the predicate resets to zero.

sleep reports, it does not force. The meta may skip any item; pending blocks nothing.

## Delayed verification: the meta feedback protocol

This is BCP's most important mechanism, and the most recently landed one.

**The problem**: Yin's PASS only means "the declaration matches the mechanical facts". It does not mean "this thing is actually useful in reality". An immunologist knows whether a gating strategy is right, but cannot read the code. That judgment can only be made by the meta, after real use — and it is inevitably late.

**The protocol**:

| Stage | Who | What |
|---|---|---|
| Task closeout | Yin | mechanical collision → on PASS, record a `claim` (snapshot of deliverables / files / acceptance anchors + commits baseline) |
| Aging | Yin | reported by **activity buckets**: <10 commits fresh (skippable) / 10–30 due for verification / >30 decidable long-term (distance in `commits`, not wall-clock) |
| Feedback | Meta | the clerk pre-fills a draft → the meta speaks plainly → Yang transcribes into a structured `judged` record |
| Attribution | Meta | defect/drift must carry an attribution layer: design / plan / implementation / environment / requirement |
| Any time | Meta | report a breakage and close it on the spot / close it proactively via `/feedback`; skipping = it stays pending |

**Core design**:

- **The clerk pre-fills, never fills in.** The agent drafts from the claim record; the meta speaks plain language; Yang translates it into a structured record.
- **Attribution layer**: the environment does not penalize the AI — "the data format changed" is not the AI's fault, it only updates the premises.
- **pending never blocks**: a claim is just a to-do marker in the ledger. The meta may close it any time, or never. A backlog of pending items is itself a signal.
- **The ledger stays append-only**: drafts live only in the conversation; only meta-confirmed records land. Recorded means confirmed.

> Why activity instead of time: BCP has no daemon, and a timer would be building a cron for meta feedback; the meta's real rhythm is "after doing enough work, look back". Full rationale in Blueprint §6.

## Meta skills: lighter with use

BCP's entry bar is genuinely high. On day one the meta needs to understand the BCP architecture, artifact phase changes, and agent systems — a double identity of "domain expert + agent architect".

**But that is day one, not the end state.**

Over long use, the meta repeatedly makes the same kind of judgments: attribution patterns, threshold calls, risk appetite, acceptance criteria, taboos. Those judgment patterns can be crystallized into **meta skills** — procedural knowledge about *how to operate BCP*.

| Stage | The meta's work | Cognitive load |
|---|---|---|
| Cold start | Judge every piece of feedback from scratch | Highest |
| Pattern accumulation | The system extracts patterns, pre-fills drafts | Falling |
| Meta-skill crystallization | High-frequency patterns are injected into feedback interviews | Stable at "domain judgment + confirmation" |
| Long term | The meta only handles unknown patterns | Keeps falling, never reaches zero |

**Stages are a description, not a mechanism** — no stage daemon is built; when crystallization happens is driven by confirmation data. Zero meta skills during cold start is the norm: no confirmation data, no crystallization (Blueprint §3).

**Meta skills only pre-fill, never fill in.** The meta always keeps the final judgment. A meta skill is a draft generator, not a decision substitute.

## Where BCP fits

BCP's three-phase loop is designed for open domains — "no human present + no ready-made judge":

| Fits | Does not fit |
|---|---|
| Fuzzy requirements, no existing tests, the AI must iterate independently over many rounds | A mature codebase with full CI/CD and test coverage |
| The human gives the design only and cannot review line by line | Scenarios where a human can pair / review line by line |
| Experience must accumulate across sessions, models, and people | One-off scripts, exploratory prototypes |

**Installing it in the wrong domain = paying the collision tax for a domain that already has its own judge.**

## What it can become

BCP is a **paradigm**, not a product.

- Writing code can use it (today's form).
- Expert Q&A can use it (treat the "answer" as the deliverable, the "hard rules" as Yin).
- Industrial layout can use it (treat the "layout plan" as the deliverable, the "interference criteria" as Yin).
- Any setting that needs **domain judgment + AI generation + mechanical verification + accumulation over time** can use it.

**Products go stale. Paradigms don't.**

## Quick start

```bash
# 1. Copy the host-independent files into your project root
#    (Blueprint.md is the paradigm spec and must be copied along)
cp -r README.md README.zh-CN.md Blueprint.md plan.md bcp .pi <your-project>/

# 2. Fill in the instance layer
#    - AGENTS.md: project index, modeled on the kit/AGENTS.template.md skeleton (≤6KB)
#    - bcp/bcp.toml: enable the project-specific rules R1–R4 as needed (unconfigured = skipped)
#    - .pi/extensions/memory-gate.ts: fill ROUTES (path → domain); an empty table means domain injection idles

# 3. Install the commit gate (the hook comes from this repo's kit/; kit/ itself is not copied)
cp <bcp-kit>/kit/pre-commit <your-project>/.git/hooks/pre-commit && chmod +x <your-project>/.git/hooks/pre-commit

# 4. Paradigm health self-check (IDLE = a gate is idling, i.e. effectively absent)
python3 bcp/check.py --selfcheck

# 5. Restart the host session, then run --selfcheck once more to confirm
```

## License and contributing

- **License**: not declared yet (currently a private repository; add a LICENSE before open-sourcing).
- **Contributing**: follow the BCP workflow — /bcp design lands a Blueprint section (two diagrams + section number, meta approval required) → /plan with anchored references → implementation → `/check` collision green. See the change workflow in [Blueprint.md](Blueprint.md).

## In one sentence

**BCP gives you a governance system for controlling AI development without reading the code.**

You describe what you want. The AI does it. Something that is not an AI checks whether the AI lied.

You approve the design, and the code must stay faithful to it. When the AI fails, the failure pattern is compressed automatically. Experience accumulates, and the system gets a regular check-up.

**All you do is domain judgment. Everything else, the system remembers, checks, and settles for you.**

---

> **BCP has no final verdict — every convention explains why, and all of it evolves with the evidence in the ledger. Changing it = changing Markdown; it takes effect next session.**
