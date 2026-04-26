# trace-insight

`trace-insight` is a small Python CLI for turning AI coding workflow traces into useful engineering feedback. It reads a simplified local JSON trace, summarizes what happened, highlights inefficient loops, and recommends how to improve the next run.

This project does not use the real Traces API. It is a local companion-style prototype that works with `sample_trace.json` or any compatible JSON file.

## What Is a Trace?

In this project, a trace is a JSON array of messages from an AI-assisted coding session. Each message represents something that happened during the workflow:

- a `user` prompt
- an `assistant` response
- a `tool` or command/action step

The format is intentionally simple so the analysis is easy to run locally and easy to adapt to exported workflow data.

## Features

- Trace overview with total messages, user prompts, assistant responses, tool actions, estimated tokens, and estimated cost
- Workflow efficiency scoring with repeated prompt patterns and retry/correction signals
- Repeated prompt detection using normalized user prompt text
- Most Expensive Prompt card showing which prompt triggered the most downstream assistant/tool work
- Diagnosis section with Likely Root Cause, Recommended Fix, and Estimated Savings
- Additional workflow suggestions for improving future AI coding sessions
- Polished terminal output with Typer and Rich

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
python3 main.py analyze sample_trace.json
```

If your shell is already using the project virtual environment, this also works:

```bash
python main.py analyze sample_trace.json
```

## Output

The report is organized into product-style sections:

1. `Trace Overview`: high-level counts and rough token/cost estimates
2. `Workflow Efficiency`: inefficiency score, repeated prompt patterns, and retry signals
3. `Most Expensive Prompt`: the user prompt that likely caused the most downstream work
4. `Diagnosis`: likely root cause, recommended fix, and estimated savings

The diagnosis section is the main action-oriented output. It tells the developer what to change next time, such as defining acceptance criteria earlier, batching related tool checks, or making the expected output more explicit.

## Input Format

The trace file should be a JSON array of messages:

```json
[
  {
    "role": "user",
    "content": "Add a Python CLI that analyzes a trace JSON file.",
    "timestamp": "2026-04-23T09:00:00Z",
    "agent": "developer"
  },
  {
    "role": "tool",
    "content": "Listed workspace files.",
    "action": "ls"
  }
]
```

Each message supports:

- `role`: `user`, `assistant`, or `tool`
- `content`: message text
- `timestamp`: optional timestamp string
- `agent`: optional agent name
- `action`: optional tool/action name

## How It Works

The analysis uses deterministic Python rules only. There are no OpenAI API calls, external models, databases, or network services.

- Token count is estimated as `characters / 4`
- Cost uses a mock blended price of `$0.003` per 1,000 tokens
- Repeated prompts are detected by lowercasing and normalizing whitespace
- Most Expensive Prompt looks at assistant responses and tool actions after each user prompt until the next user prompt
- Inefficiency score combines repeated prompts, extra tool steps, long traces, and correction words like `again`, `still`, `fix`, `retry`, and `same error`
- Diagnosis rules map repeated prompts, tool volume, and inefficiency score to a likely root cause and recommended fix

## Why This Matters for AI Coding Workflows

AI coding sessions can fail in subtle ways: the model may retry the same issue, rerun commands without new information, or spend tokens compensating for unclear acceptance criteria. `trace-insight` helps convert that workflow history into concrete feedback so the next run starts with clearer instructions and less wasted back-and-forth.

## Project Files

- `main.py`: Typer CLI and analysis logic
- `sample_trace.json`: realistic inefficient trace for exercising the report
- `requirements.txt`: Python dependencies
