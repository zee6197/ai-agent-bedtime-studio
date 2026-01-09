# Bedtime Story Studio (LLM + Judge Loop)

## Overview
Bedtime Story Studio is a personal project exploring how to generate high-quality, age-appropriate bedtime stories using large language models and an automated evaluation loop.

The system takes a simple bedtime story request and produces a story tailored for children ages 5–10. To improve consistency and quality, it incorporates a **judge agent** that critiques generated stories and requests revisions when necessary.

The main goals of this project were to experiment with:
- Prompt design and iteration
- Agent-style feedback loops
- Balancing creativity with safety constraints
- Building a simple but resilient CLI-based AI system

---

## Features
- Interactive CLI for collecting story preferences (idea, characters, tone, lesson, length)
- Structured story generation with enforced format and pacing
- Automated judge agent that evaluates stories for:
  - Age appropriateness
  - Coherence
  - Alignment with user intent
  - Creativity
- Iterative refinement loop based on judge feedback
- Transparent display of judge verdicts and reasoning
- Graceful handling of invalid inputs and retries

---

## System Design
At a high level, the application runs a lightweight agent loop:

1. Collects user preferences
2. Generates a structured story draft
3. Evaluates the draft using a judge prompt
4. Revises the story if needed
5. Returns an approved (or best-effort) story


### Block diagram

```
┌──────────────┐      preferences      ┌───────────────┐   story draft   ┌────────────┐
│    User      │ ───────────────────▶ │ Storyteller   │ ───────────────▶ │   Judge     │
│ (CLI input)  │                      │  Agent        │                  │  Agent      │
└─────┬────────┘                      └─────┬─────────┘                  └────┬────────┘
      │ paraphrased summary                │ critique / constraints            │ verdict JSON
      │                                    │                                    │
      │                    optional tweak  │                                    │
      └────────────────────────────────────┴────────────────────────────────────┘
                               approved story ↺ revise loop
```

## How It Works

### Storyteller Agent
- Uses a structured prompt that enforces:
  - A clear title
  - A coherent story arc
  - Age-appropriate vocabulary
  - Gentle pacing suitable for bedtime
  - An explicit moral or lesson
- Incorporates feedback from prior judge critiques when revising drafts to improve quality and alignment

### Judge Agent
- Evaluates each story draft and returns a structured JSON response containing:
  - `verdict` (`approve` or `revise`)
  - `issues`
  - `suggestions`
- Focuses on tone, safety, clarity, coherence, and suitability for children ages 5–10

The system runs for a limited number of iterations to avoid infinite retry loops while still improving story quality.

---

## Running the Project

```bash
export OPENAI_API_KEY=sk-...   # use your own key
python main.py
```

Follow the guided prompts in the CLI.  
After the final story is generated, the judge’s evaluation is printed for transparency.

---

## Example CLI Flow

```text

Welcome to the Bedtime Story Studio!
Config — Story temp: 0.65, Judge temp: 0.2, Attempts: 2

What is the main idea or request for the story?
A cozy bedtime adventure about a curious otter who wants to see the northern lights.

Generating story draft #1...
Judge verdict: APPROVE — A charming and enchanting bedtime story suitable for young readers.
```

## Quality & Reliability

- Input validation prevents low-signal or malformed prompts
- Retry and backoff logic for API calls
- JSON validation for judge outputs
- Session logging for debugging and iteration
- Unit tests for helper utilities and parsing logic
- Run tests with:

```bash
  python -m unittest tests/test_utils.py
```

## Future Improvements

If I were to continue developing this project, I would:

- Add an automated evaluation harness for regression testing prompts
- Build a lightweight web UI to visualize stories and judge feedback
- Support additional content types (poems, lullabies, interactive stories)
- Further modularize storyteller and judge logic for reuse across interfaces

## Motivation

This project was built as a hands-on way to better understand:

- Prompt engineering tradeoffs
- Agent-style system design
- How to enforce constraints without sacrificing creativity
- Designing AI systems that are both useful and safe for real users
