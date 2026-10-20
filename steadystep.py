#!/usr/bin/env python3
"""SteadyStep: one small local-AI action at a time.

Hacktoberfest 2026 Week 3 — Slow and Steady.
Uses a local open-weight Gemma model through Ollama to turn a goal and
recent progress into exactly one realistic next step.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

APP_DIR = Path.home() / ".steadystep"
STATE_PATH = APP_DIR / "state.json"
OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "gemma3:1b"
VALID_MINUTES = (5, 10, 15, 20, 30, 45, 60)


class SteadyStepError(RuntimeError):
    pass


@dataclass
class Plan:
    title: str
    action: str
    done_when: str
    why_now: str
    encouragement: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Plan":
        expected = {"title", "action", "done_when", "why_now", "encouragement"}
        if set(data) != expected:
            raise SteadyStepError("Model output did not match the required plan schema.")
        if not all(isinstance(data[k], str) and data[k].strip() for k in expected):
            raise SteadyStepError("Model output contained an empty or invalid field.")
        return cls(**{k: data[k].strip() for k in expected})

    def as_dict(self) -> dict[str, str]:
        return {
            "title": self.title,
            "action": self.action,
            "done_when": self.done_when,
            "why_now": self.why_now,
            "encouragement": self.encouragement,
        }


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_state(path: Path = STATE_PATH) -> dict[str, Any]:
    if not path.exists():
        return {"goal": None, "history": [], "pending": None}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SteadyStepError(f"Could not read state file: {path}") from exc
    if not isinstance(data, dict):
        raise SteadyStepError("State file is not a JSON object.")
    data.setdefault("goal", None)
    data.setdefault("history", [])
    data.setdefault("pending", None)
    return data


def save_state(state: dict[str, Any], path: Path = STATE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def compact_history(state: dict[str, Any], limit: int = 6) -> list[dict[str, Any]]:
    history = state.get("history", [])
    if not isinstance(history, list):
        return []
    out = []
    for item in history[-limit:]:
        if not isinstance(item, dict):
            continue
        out.append({
            "title": str(item.get("plan", {}).get("title", ""))[:80],
            "action": str(item.get("plan", {}).get("action", ""))[:240],
            "outcome": str(item.get("outcome", ""))[:240],
        })
    return out


def build_prompt(goal: str, minutes: int, history: list[dict[str, Any]]) -> str:
    history_json = json.dumps(history, ensure_ascii=False)
    return f"""
You are SteadyStep, a local progress coach. Your job is NOT to make a big plan.
Give the user exactly ONE small, concrete next action that can be completed in
at most {minutes} minutes and moves this goal forward:

GOAL: {goal}

Recent completed steps, newest last:
{history_json}

Rules:
- Return one action only, not a checklist and not multiple alternatives.
- Prefer a smaller action over an ambitious one. "Slow and steady" is the design rule.
- If history exists, build naturally on it without repeating completed work.
- The action must be specific enough to start immediately.
- It must fit inside {minutes} minutes without pretending a huge task can be finished.
- Never give medical, legal, financial, self-harm, weapon, or other high-stakes advice.
  For such goals, return a safe action to contact an appropriate qualified professional.
- Do not invent facts about the user's progress.
- Keep every field concise.

Return ONLY valid JSON with exactly these keys:
{{
  "title": "2-6 word label",
  "action": "one concrete action, max 35 words",
  "done_when": "an observable completion condition, max 22 words",
  "why_now": "why this is the right small next step, max 24 words",
  "encouragement": "one calm sentence, no hype"
}}
""".strip()


def call_ollama(model: str, prompt: str, url: str = OLLAMA_URL) -> Plan:
    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.35},
    }).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            outer = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise SteadyStepError(
            f"Could not reach Ollama at {url}. Run `ollama serve` and "
            f"`ollama pull {model}` first."
        ) from exc
    except json.JSONDecodeError as exc:
        raise SteadyStepError("Ollama returned invalid JSON.") from exc

    if not isinstance(outer, dict):
        raise SteadyStepError("Ollama returned a non-object response.")
    raw = outer.get("response")
    if not isinstance(raw, str) or not raw.strip():
        raise SteadyStepError("Ollama returned an empty model response.")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SteadyStepError("The model response was not valid JSON.") from exc
    if not isinstance(data, dict):
        raise SteadyStepError("The model response was not a JSON object.")
    return Plan.from_dict(data)


def sample_plan() -> Plan:
    return Plan(
        title="Open One File",
        action="Open the project README and write three bullets describing what the user should be able to do when the project is finished.",
        done_when="The README contains three clear outcome bullets.",
        why_now="A tiny definition of done prevents the next coding session from wandering.",
        encouragement="One clear step is enough for today.",
    )


def render(plan: Plan, goal: str, minutes: int, model_label: str) -> str:
    return "\n".join([
        "🦥 SteadyStep",
        f"Goal: {goal}",
        f"Budget: {minutes} min  •  {model_label}",
        "",
        f"NEXT: {plan.title}",
        plan.action,
        "",
        f"Done when: {plan.done_when}",
        f"Why now: {plan.why_now}",
        "",
        plan.encouragement,
        "",
        "No backlog. No ten-step plan. Finish this one thing, then come back.",
    ])


def command_plan(args: argparse.Namespace, state_path: Path = STATE_PATH) -> int:
    state = load_state(state_path)
    goal = (args.goal or state.get("goal") or "").strip()
    if not goal:
        raise SteadyStepError("Provide a goal with --goal the first time you run SteadyStep.")

    if state.get("pending") and not args.replace:
        pending = state["pending"]
        plan = Plan.from_dict(pending["plan"])
        print(render(plan, state["goal"], pending["minutes"], pending["model_label"]))
        print("\nA step is already pending. Run `python steadystep.py done --outcome \"...\"` or use --replace.")
        return 0

    if state.get("goal") and goal != state["goal"]:
        raise SteadyStepError("For a different goal, use --state with a separate state file to keep progress independent.")
    history = compact_history(state)
    if args.sample:
        plan = sample_plan()
        label = "SAMPLE (no AI call)"
    else:
        plan = call_ollama(args.model, build_prompt(goal, args.minutes, history))
        label = f"local {args.model} via Ollama"

    state["goal"] = goal
    state["pending"] = {
        "created_at": utc_now(),
        "minutes": args.minutes,
        "model_label": label,
        "plan": plan.as_dict(),
    }
    save_state(state, state_path)
    print(render(plan, goal, args.minutes, label))
    return 0


def command_done(args: argparse.Namespace, state_path: Path = STATE_PATH) -> int:
    state = load_state(state_path)
    pending = state.get("pending")
    if not pending:
        raise SteadyStepError("There is no pending step. Run `plan` first.")
    outcome = args.outcome.strip()
    if not outcome:
        raise SteadyStepError("Outcome cannot be empty.")
    state.setdefault("history", []).append({
        "completed_at": utc_now(),
        "plan": pending["plan"],
        "outcome": outcome,
    })
    state["pending"] = None
    save_state(state, state_path)
    print("✅ Step recorded. That is enough for this round.")
    print("Run `python steadystep.py plan` when you want the next small step.")
    return 0


def command_status(args: argparse.Namespace, state_path: Path = STATE_PATH) -> int:
    state = load_state(state_path)
    history = state.get("history", [])
    print("🦥 SteadyStep status")
    print(f"Goal: {state.get('goal') or '(not set)'}")
    print(f"Completed steps: {len(history) if isinstance(history, list) else 0}")
    if state.get("pending"):
        p = state["pending"]
        print(f"Pending: {p['plan']['title']} — {p['plan']['action']}")
    else:
        print("Pending: none")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="One small local-AI step at a time.")
    parser.add_argument("--state", type=Path, default=STATE_PATH, help="Progress file (use a separate file for each goal)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("plan", help="Generate exactly one next step")
    p.add_argument("--goal", help="Goal to make slow, steady progress on")
    p.add_argument("--minutes", type=int, choices=VALID_MINUTES, default=15)
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--sample", action="store_true", help="Use a clearly labelled non-AI sample")
    p.add_argument("--replace", action="store_true", help="Replace an unfinished pending step")

    d = sub.add_parser("done", help="Record completion of the pending step")
    d.add_argument("--outcome", required=True, help="What actually happened")

    sub.add_parser("status", help="Show local progress")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "plan":
            return command_plan(args, args.state)
        if args.command == "done":
            return command_done(args, args.state)
        return command_status(args, args.state)
    except SteadyStepError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
