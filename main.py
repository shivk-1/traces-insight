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
    cost = tokens / 1000 * COST_PER_1K_TOKENS

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


@app.command()
def analyze(trace_file: Path) -> None:
    """Analyze an exported AI coding trace JSON file."""
    messages = load_trace(trace_file)
    metrics = analyze_trace(messages)
    render_report(trace_file, metrics)


if __name__ == "__main__":
    app()
