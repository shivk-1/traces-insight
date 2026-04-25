<img width="1268" height="474" alt="Screenshot 2026-04-24 at 1 10 06 PM" src="https://github.com/user-attachments/assets/41e163aa-46db-4062-acfa-9f5eac4705c9" />

# trace-insight

`trace-insight` is a tiny Python CLI prototype for analyzing AI coding workflow
traces. It is designed as a companion idea for Traces: after a developer captures
a session, they can run this tool to spot inefficiencies, repeated prompts, rough
cost, and practical ways to improve the next run.

This project does not use the Traces API. It reads a local JSON file.

## Features

- Counts user prompts, assistant responses, and tool/action steps
- Detects repeated user prompts
- Identifies the most expensive prompt by downstream assistant/tool work
- Estimates token count and mock cost
- Calculates an inefficiency score from 0-100
- Prints a concise trace summary
- Suggests 3 practical workflow improvements
- Uses Rich tables and panels for polished terminal output

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Demo

```bash
python main.py analyze sample_trace.json
```

If you do not activate the virtual environment, run:

```bash
.venv/bin/python main.py analyze sample_trace.json
```

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

The code keeps the analysis intentionally simple for an interview demo:

- Token count is estimated as `characters / 4`
- Cost uses a mock blended price of `$0.003` per 1,000 tokens
- Repeated prompts are detected by lowercasing and normalizing whitespace
- Most expensive prompt looks at assistant responses and tool actions triggered
  after each user prompt before the next user prompt
- Inefficiency score combines repeated prompts, extra tool steps, long traces,
  and correction words like `again`, `still`, `fix`, and `same error`

## Project Files

- `main.py`: Typer CLI and analysis logic
- `sample_trace.json`: intentionally inefficient trace for demoing insights
- `requirements.txt`: Python dependencies to download
