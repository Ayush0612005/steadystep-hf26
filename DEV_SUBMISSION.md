# SteadyStep: a local AI that refuses to give me a 30-item productivity plan 🦥

Hacktoberfest Open-Source AI Challenge Week 3: Slow and Steady Submission 🦥

*This is a submission for the [Hacktoberfest Open-Source AI Challenge Week 3: Slow and Steady](https://dev.to/challenges/hacktoberfest-week3-2026-10-19).*

## What I Built

I built **SteadyStep**, a tiny local-first CLI with one rule: it is allowed to give me **one next step**, not a productivity manifesto.

I give it a goal and a time budget. A local Gemma model looks at the goal plus the last few things I actually completed and chooses one concrete action that fits inside that time. I finish it, record what happened, and only then can it generate the next step.

The loop is intentionally simple:

```text
set a goal → get one small step → do it → record outcome → repeat
```

For example:

```bash
python steadystep.py plan \
  --goal "learn binary search trees in C" \
  --minutes 15
```

The response is constrained to one action, one observable completion condition, and one short explanation of why that step makes sense now.

When I finish:

```bash
python steadystep.py done \
  --outcome "Implemented insert() and tested three nodes"
```

The next planning call sees that result, so it can move forward instead of starting from generic advice again.

The lazy payoff is that I never have to turn “I should work on this” into a giant backlog before I can begin. I only decide once: what goal matters. SteadyStep handles the tiny next decision from there.

## Demo

The repository includes `demo.gif`, an animated recording of actual CLI sample-mode output through plan → done → status. It is explicitly a non-AI interface demonstration; live Gemma inference has not been tested in the publishing environment.

The project has a clearly labelled sample mode that demonstrates the interface without pretending static output came from AI:

```bash
python steadystep.py --state demo-state.json plan \
  --goal "ship a tiny CLI" --minutes 10 --sample
```

It produces a single card like:

```text
🦥 SteadyStep
Goal: ship a tiny CLI
Budget: 10 min  •  SAMPLE (no AI call)

NEXT: Open One File
Open the project README and write three bullets describing what the user should be able to do when the project is finished.

Done when: The README contains three clear outcome bullets.
Why now: A tiny definition of done prevents the next coding session from wandering.

One clear step is enough for today.

No backlog. No ten-step plan. Finish this one thing, then come back.
```

## Code

GitHub: https://github.com/Ayush0612005/steadystep-hf26

## How I Built It

SteadyStep is deliberately small.

- Python standard library for the CLI, JSON state, and HTTP call.
- Ollama on localhost for inference.
- Gemma 3 (`gemma3:1b`) as the default open-weight model.
- A strict JSON output contract with five short fields.
- A local state file containing the goal, current pending step, and completed history.
- Only the latest six completed steps go back into the prompt, so the context stays focused instead of growing forever.

The model is the core of the project. Without the model, there is no adaptive next-step selection: it is what looks at the goal, the time available, and what happened in previous steps and chooses what should happen next.

I also made the CLI refuse to silently replace unfinished work. If a step is still pending, `plan` shows the same step again unless I explicitly pass `--replace`. That little constraint turned out to be important to the theme: the tool should encourage steady completion rather than constantly generating exciting new plans.

Local state is written atomically through a temporary file, and the project includes unit tests for persistence, schema validation, context limits, and pending-step reuse.

## Why Does Open Innovation Matter?

The most personal part of this tool is not the goal itself; it is the history of what I tried, what I finished, and what I did not finish.

That is exactly the kind of context I do not want to send to a hosted model every time I ask what to do next.

Running an open-weight Gemma model through Ollama means the planning loop can stay on the user's machine. There is no per-step API bill, no required cloud account, and no reason for a private progress journal to leave localhost.

Open weights also make the project genuinely modifiable. The prompt is visible. The model can be swapped. The output constraints can be changed. Someone can fork SteadyStep and tune it for studying, open-source maintenance, writing, or another low-stakes workflow without waiting for a closed service to expose a feature.

For a “slow and steady” tool, that independence matters: set it up once, keep using it, and let the small steps accumulate.

## AI Build Disclosure

This project was built with an AI coding agent operating on my behalf. The agent checked the challenge requirements and ran nine automated tests covering local state and mocked model-response handling. The build and write-up use the **Fully Autonomous** disclosure. The sample demonstration is not evidence of a live Gemma run.

## Prize Categories

- Best Use of Gemma: Gemma 3 via Ollama is the default local planning model.

## What I Learned

The interesting part was not making the model produce a better long-term plan. It was designing the program so the model **could not** keep expanding the plan.

A few constraints made the idea work:

1. Exactly one next action.
2. A requested time budget (a model instruction, not a guaranteed duration).
3. An observable “done when” condition.
4. A pending step is reused instead of regenerated by default.
5. Only completed outcomes become progress context.

That makes the AI less impressive in a single screenshot, but much more useful as a quiet loop I can come back to.

#devchallenge #hf26challenge #ai #opensource
