"""trace-insight: summarize AI coding workflow traces from JSON.

This prototype intentionally avoids any real Traces API integration. It works
with a simple exported JSON file so the core idea is easy to demo and explain.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table


app = typer.Typer(help="Analyze AI coding trace JSON files.")
console = Console()

# 1 token is roughly 4 characters, and this prototype uses a blended mock price (price can be put in later)
CHARS_PER_TOKEN = 4
COST_PER_1K_TOKENS = 0.003


@app.callback()
def main() -> None:
    """Trace insight commands."""


def normalize_prompt(text: str) -> str:
    """Normalize prompts so tiny spacing/case changes do not hide repeats."""
    return re.sub(r"\s+", " ", text.strip().lower())


def estimate_tokens(messages: list[dict[str, Any]]) -> int:
    """Estimate token usage with a common rough heuristic."""
    total_chars = sum(len(str(message.get("content", ""))) for message in messages)
    return max(1, round(total_chars / CHARS_PER_TOKEN))


def estimate_cost(tokens: int) -> float:
    """Estimate cost using the project's mock blended token price."""
    return tokens / 1000 * COST_PER_1K_TOKENS


def describe_cost_impact(action_count: int, cost: float) -> str:
    """Convert rough downstream work into an interview-friendly label."""
    if action_count >= 4 or cost >= 0.001:
        return "High"
    if action_count >= 2 or cost >= 0.0005:
        return "Medium"
    return "Low"


def load_trace(path: Path) -> list[dict[str, Any]]:
    """Load and validate the minimal JSON shape expected by the CLI."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise typer.BadParameter(f"File not found: {path}") from None
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"Invalid JSON: {exc}") from exc

    if not isinstance(data, list):
        raise typer.BadParameter("Trace must be a JSON array of messages.")

    for index, message in enumerate(data, start=1):
        if not isinstance(message, dict):
            raise typer.BadParameter(f"Message {index} must be an object.")
        if message.get("role") not in {"user", "assistant", "tool"}:
            raise typer.BadParameter(
                f"Message {index} must have role user, assistant, or tool."
            )
        if not isinstance(message.get("content", ""), str):
            raise typer.BadParameter(f"Message {index} content must be a string.")

    return data


def find_most_expensive_prompt(messages: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Find the user prompt that triggered the most downstream trace activity.

    The heuristic is intentionally simple: each user prompt owns the assistant
    responses and tool actions after it until the next user prompt appears.
    """
    most_expensive: dict[str, Any] | None = None

    for index, message in enumerate(messages):
        if message["role"] != "user":
            continue

        downstream = []
        for next_message in messages[index + 1 :]:
            if next_message["role"] == "user":
                break
            if next_message["role"] in {"assistant", "tool"}:
                downstream.append(next_message)

        action_count = len(downstream)
        downstream_tokens = estimate_tokens(downstream) if downstream else 0
        downstream_cost = estimate_cost(downstream_tokens)
        score = action_count * 10 + downstream_tokens

        candidate = {
            "prompt": message.get("content", ""),
            "action_count": action_count,
            "estimated_tokens": downstream_tokens,
            "estimated_cost": downstream_cost,
            "cost_impact": describe_cost_impact(action_count, downstream_cost),
            "score": score,
        }

        if most_expensive is None or candidate["score"] > most_expensive["score"]:
            most_expensive = candidate

    return most_expensive


def analyze_trace(messages: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute practical metrics from the trace messages."""
    role_counts = Counter(message["role"] for message in messages)
    user_prompts = [message for message in messages if message["role"] == "user"]
    tool_steps = [message for message in messages if message["role"] == "tool"]

    prompt_counts = Counter(
        normalize_prompt(message.get("content", "")) for message in user_prompts
    )
    repeated_prompts = {
        prompt: count for prompt, count in prompt_counts.items() if count > 1
    }

    tokens = estimate_tokens(messages)
    cost = estimate_cost(tokens)
    most_expensive_prompt = find_most_expensive_prompt(messages)

    repeat_penalty = min(35, sum(repeated_prompts.values()) * 8)
    tool_penalty = min(25, max(0, len(tool_steps) - len(user_prompts)) * 5)
    long_trace_penalty = min(20, max(0, len(messages) - 10) * 2)
    correction_penalty = min(
        20,
        sum(
            5
            for message in user_prompts
            if any(
                marker in normalize_prompt(message.get("content", ""))
                for marker in ["again", "still", "fix", "retry", "same error"]
            )
        ),
    )
    inefficiency_score = min(
        100, repeat_penalty + tool_penalty + long_trace_penalty + correction_penalty
    )

    return {
        "total_messages": len(messages),
        "user_prompts": role_counts["user"],
        "assistant_responses": role_counts["assistant"],
        "tool_steps": role_counts["tool"],
        "repeated_prompts": repeated_prompts,
        "estimated_tokens": tokens,
        "estimated_cost": cost,
        "inefficiency_score": inefficiency_score,
        "most_expensive_prompt": most_expensive_prompt,
    }


def build_summary(metrics: dict[str, Any]) -> str:
    """Turn metrics into a short human-readable trace summary."""
    repeated_count = len(metrics["repeated_prompts"])
    return (
        f"This trace contains {metrics['total_messages']} messages with "
        f"{metrics['tool_steps']} tool/action steps. "
        f"It shows {repeated_count} repeated user prompt pattern(s), "
        f"which suggests avoidable back-and-forth during the coding workflow."
    )


def build_suggestions(metrics: dict[str, Any]) -> list[str]:
    """Generate practical coaching suggestions from the metric profile."""
    suggestions = []

    if metrics["repeated_prompts"]:
        suggestions.append(
            "Consolidate repeated prompts into one clearer instruction with expected output."
        )
    if metrics["tool_steps"] > metrics["user_prompts"]:
        suggestions.append(
            "Batch related file inspection commands before asking the agent to revise code."
        )
    if metrics["inefficiency_score"] >= 50:
        suggestions.append(
            "Add acceptance criteria before implementation so the agent can self-check earlier."
        )

    fallback_suggestions = [
        "Ask the assistant to summarize its plan before running many tool actions.",
        "Capture failing command output once, then reference it instead of re-running blindly.",
        "End the trace with a short retrospective to preserve lessons for the next session.",
    ]

    for suggestion in fallback_suggestions:
        if len(suggestions) == 3:
            break
        if suggestion not in suggestions:
            suggestions.append(suggestion)

    return suggestions[:3]


def build_ai_fix_diagnosis(metrics: dict[str, Any]) -> dict[str, str]:
    """Diagnose the likely workflow issue and recommend a concrete fix.

    This is deterministic on purpose: it makes the prototype feel intelligent
    while staying easy to explain in an interview.
    """
    repeated_prompt_types = len(metrics["repeated_prompts"])
    repeated_prompt_count = sum(metrics["repeated_prompts"].values())
    tool_steps_are_high = metrics["tool_steps"] > metrics["user_prompts"]
    inefficiency_is_high = metrics["inefficiency_score"] >= 50

    if repeated_prompt_types > 1 or repeated_prompt_count > 2:
        root_cause = (
            "The workflow likely started from an underspecified prompt, causing "
            "repeated clarification and correction loops."
        )
    elif tool_steps_are_high:
        root_cause = (
            "The agent spent too much effort rediscovering context through "
            "scattered tool actions."
        )
    elif inefficiency_is_high:
        root_cause = (
            "Validation happened late in the workflow, so the agent corrected "
            "issues after implementation instead of preventing them upfront."
        )
    else:
        root_cause = (
            "The trace looks mostly healthy, with a small opportunity to make "
            "the initial request more precise."
        )

    fix_steps = ["Define expected output before implementation."]
    if inefficiency_is_high or repeated_prompt_types:
        fix_steps.append("Add acceptance criteria before implementation:")
        fix_steps.extend(
            [
                "- expected output format",
                "- exact file to modify",
                "- clear success condition",
            ]
        )
    if tool_steps_are_high:
        fix_steps.append("Batch related file reads and command checks before asking for revisions.")
    if not inefficiency_is_high and not repeated_prompt_types and not tool_steps_are_high:
        fix_steps.append("Ask the agent to state its plan and success check before editing.")

    if metrics["inefficiency_score"] >= 50:
        savings = "~30% fewer retries\n~40% lower token cost"
    elif metrics["inefficiency_score"] >= 25:
        savings = "~15% fewer retries\n~20% lower token cost"
    else:
        savings = "~5% fewer retries\n~10% lower token cost"

    return {
        "root_cause": root_cause,
        "recommended_fix": "\n".join(fix_steps),
        "estimated_savings": savings,
    }


def render_report(path: Path, metrics: dict[str, Any]) -> None:
    """Render the analysis using Rich tables and panels."""
    console.print()
    console.print(
        Panel.fit(
            f"[bold cyan]trace-insight[/bold cyan]\n[white]{path}[/white]",
            border_style="cyan",
        )
    )

    table = Table(title="Trace Metrics", show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Value", justify="right")
    table.add_row("Total messages", str(metrics["total_messages"]))
    table.add_row("User prompts", str(metrics["user_prompts"]))
    table.add_row("Assistant responses", str(metrics["assistant_responses"]))
    table.add_row("Tool/action steps", str(metrics["tool_steps"]))
    table.add_row("Estimated tokens", f"{metrics['estimated_tokens']:,}")
    table.add_row("Estimated cost", f"${metrics['estimated_cost']:.4f}")
    table.add_row("Inefficiency score", f"{metrics['inefficiency_score']}/100")
    console.print(table)

    repeated_table = Table(
        title="Repeated User Prompts", show_header=True, header_style="bold yellow"
    )
    repeated_table.add_column("Prompt")
    repeated_table.add_column("Count", justify="right")

    if metrics["repeated_prompts"]:
        for prompt, count in metrics["repeated_prompts"].items():
            repeated_table.add_row(prompt, str(count))
    else:
        repeated_table.add_row("[dim]No repeated prompts found[/dim]", "0")
    console.print(repeated_table)

    expensive_prompt = metrics["most_expensive_prompt"]
    if expensive_prompt:
        expensive_text = (
            f'[bold]Prompt:[/bold] "{expensive_prompt["prompt"]}"\n'
            "[bold]Assistant/tool actions triggered:[/bold] "
            f"{expensive_prompt['action_count']}\n"
            "[bold]Estimated downstream tokens:[/bold] "
            f"{expensive_prompt['estimated_tokens']:,}\n"
            "[bold]Estimated Cost Impact:[/bold] "
            f"{expensive_prompt['cost_impact']} "
            f"(${expensive_prompt['estimated_cost']:.4f})"
        )
    else:
        expensive_text = "[dim]No user prompts found in this trace.[/dim]"

    console.print(
        Panel(
            expensive_text,
            title="Most Expensive Prompt",
            border_style="red",
        )
    )

    console.print(
        Panel(
            build_summary(metrics),
            title="Trace Summary",
            border_style="green",
        )
    )

    suggestions = "\n".join(
        f"[bold]{index}.[/bold] {suggestion}"
        for index, suggestion in enumerate(build_suggestions(metrics), start=1)
    )
    console.print(
        Panel(
            suggestions,
            title="3 Practical Improvement Suggestions",
            border_style="blue",
        )
    )

    diagnosis = build_ai_fix_diagnosis(metrics)
    diagnosis_text = (
        f"[bold red]Likely Root Cause:[/bold red]\n"
        f"{diagnosis['root_cause']}\n\n"
        f"[bold green]Recommended Fix:[/bold green]\n"
        f"{diagnosis['recommended_fix']}\n\n"
        f"[bold cyan]Estimated Savings:[/bold cyan]\n"
        f"{diagnosis['estimated_savings']}"
    )
    console.print(
        Panel(
            diagnosis_text,
            title="AI Fix Suggestions",
            border_style="bright_magenta",
        )
    )


@app.command()
def analyze(trace_file: Path) -> None:
    """Analyze an exported AI coding trace JSON file."""
    messages = load_trace(trace_file)
    metrics = analyze_trace(messages)
    render_report(trace_file, metrics)


if __name__ == "__main__":
    app()
