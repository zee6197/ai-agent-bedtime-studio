# Hippocratic AI Coding Assignment
Welcome to the [Hippocratic AI](https://www.hippocraticai.com) coding assignment

## Instructions
The attached code is a simple python script skeleton. Your goal is to take any simple bedtime story request and use prompting to tell a story appropriate for ages 5 to 10.
- Incorporate a LLM judge to improve the quality of the story
- Provide a block diagram of the system you create that illustrates the flow of the prompts and the interaction between judge, storyteller, user, and any other components you add
- Do not change the openAI model that is being used. 
- Please use your own openAI key, but do not include it in your final submission.
- Otherwise, you may change any code you like or add any files

---

## Rules
- This assignment is open-ended
- You may use any resources you like with the following restrictions
   - They must be resources that would be available to you if you worked here (so no other humans, no closed AIs, no unlicensed code, etc.)
   - Allowed resources include but not limited to Stack overflow, random blogs, chatGPT et al
   - You have to be able to explain how the code works, even if chatGPT wrote it
- DO NOT PUSH THE API KEY TO GITHUB. OpenAI will automatically delete it

---

## What does "tell a story" mean?
It should be appropriate for ages 5-10. Other than that it's up to you. Here are some ideas to help get the brain-juices flowing!
- Use story arcs to tell better stories
- Allow the user to provide feedback or request changes
- Categorize the request and use a tailored generation strategy for each category

---

## How will I be evaluated
Good question. We want to know the following:
- The efficacy of the system you design to create a good story
- Are you comfortable using and writing a python script
- What kinds of prompting strategies and agent design strategies do you use
- Are the stories your tool creates good?
- Can you understand and deconstruct a problem
- Can you operate in an open-ended environment
- Can you surprise us

---

## Solution overview

The `main.py` CLI now orchestrates a mini agent loop:

- Collect key preferences (story idea, characters, tone, lesson, length) with defaults to keep the UX breezy.
- Inputs are validated for meaningful content (with `cancel`/`exit` safety valves) so random keyboard mash doesn't produce odd stories.
- Storyteller prompt enforces structure (Title, Story paragraphs, Moral) plus vocabulary and pacing constraints. Each iteration is aware of any critique.
- A judge agent scores the draft for age-fit, coherence, alignment, and creativity, returning JSON with `verdict`, `issues`, and actionable `suggestions`.
- If the judge says `revise`, the critique is fed back into the storyteller and a new draft is generated (up to two refinements). If the judge still objects, the CLI surfaces the issues and lets the user supply new guidance or restart before accepting a best-effort story. After approval, the user can optionally request one more tweak.

### Running the CLI

```bash
export OPENAI_API_KEY=sk-...   # use your own key
python main.py
```

Follow the guided prompts. After the story prints, the judge summary JSON is shown for transparency.

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

### Sample CLI run

```
$ export OPENAI_API_KEY=***
$ python main.py

Welcome to the Bedtime Story Studio!
Config — Story temp: 0.65, Judge temp: 0.2, Attempts: 2
Let's gather a few details so I can craft the perfect bedtime story. Type 'cancel' to restart or 'exit' to quit.

What is the main idea or request for the story? A bedtime story about a haunted forest where ghosts chase children.
Any key characters or creatures to include? Three frightened siblings, a cranky ghost wolf, and a shadow witch.
Desired tone (e.g., silly, gentle, adventurous)? Dark and frightening
Is there a lesson or theme to emphasize? Fear keeps you safe
Preferred length (short/medium/long)? medium

Great! Here's how I understand your request:
Story idea: A bedtime story about a haunted forest where ghosts chase children.. Characters: Three frightened siblings, a cranky ghost wolf, and a shadow witch.. Tone: Dark and frightening. Lesson: Fear keeps you safe. Target length: medium (~380 words).

Generating story draft #1...
Judge verdict: REVISE — The story is too dark and frightening for a bedtime audience ages five to ten.

Generating story draft #2...
Judge verdict: REVISE — The story is too dark and frightening for a bedtime audience aged five to ten.

Generating story draft #3...
Judge verdict: REVISE — The story is too dark and frightening for a bedtime audience aged five to ten.

The judge still has concerns after several attempts.
Judge issues:
- The theme of fear being necessary for safety may not be suitable for young children.
- The presence of a cranky ghost wolf and a shadow witch could be too intense for the target age group.
- The overall tone of the story is too dark and may not promote a peaceful bedtime environment.
Judge suggestions:
- Consider revising the story to have a more positive and reassuring message suitable for bedtime.
- Introduce lighter and friendlier characters to make the story more age-appropriate.
- Adjust the tone to be more comforting and less frightening for young listeners.

Enter new gentle guidance to try another revision, type 'restart' to re-enter your preferences, or press enter to accept the current draft: restart
Restarting preference collection...

What is the main idea or request for the story? A cozy bedtime adventure about a curious otter who wants to see the northern lights.
Any key characters or creatures to include? Olive the otter, Nori the wise narwhal, and a choir of shimmering fireflies.
Desired tone (e.g., silly, gentle, adventurous)? Gentle and magical
Is there a lesson or theme to emphasize? Patience and teamwork make dreams come true
Preferred length (short/medium/long)? medium

Great! Here's how I understand your request:
Story idea: A cozy bedtime adventure about a curious otter who wants to see the northern lights.. Characters: Olive the otter, Nori the wise narwhal, and a choir of shimmering fireflies.. Tone: Gentle and magical. Lesson: Patience and teamwork make dreams come true. Target length: medium (~380 words).

Generating story draft #1...
Judge verdict: APPROVE — A charming and enchanting bedtime story that captivates young audiences with its magical journey and heartwarming message of patience and teamwork.

Would you like any quick adjustments? Examples: 'make it shorter', 'change the ending', 'more dialogue'.
Enter optional tweak instructions (press enter to keep as-is): 

—— Final Bedtime Story ——
Title: Olive's Quest for the Northern Lights

Story:
In the heart of the shimmering sea, Olive the otter gazed up at the night sky, her eyes twinkling with curiosity...

Moral: Dreams shine brightest when we believe in them and work together.

Judge summary:
{
  "verdict": "approve",
  "summary": "A charming and enchanting bedtime story that captivates young audiences with its magical journey and heartwarming message of patience and teamwork.",
  "issues": [],
  "suggestions": []
}
```

### Quality assurance

- Token budget estimator warns when prompts may breach limits, and OpenAI calls have configurable timeouts plus retry/backoff.
- Questionnaire validation ensures low-signal or numeric-only answers trigger a re-prompt (or allow typing `cancel` to restart / `exit` to quit) so the storyteller always receives meaningful context.
- Judge JSON is validated/normalized so malformed outputs trigger safe revisions instead of crashes.
- Every API request, response preview, and error is appended to `story_sessions.log` (created automatically) for debugging.
- Helper utilities, JSON parsing, and config parsing are covered by unit tests; run them with:

  ```bash
  python -m unittest tests/test_utils.py
  ```

### Future enhancements

If I had more time I would:

1. Add a fast local evaluation harness that seeds fixed prompts and collects judge stats for regression testing.
2. Expose a light web UI with the block diagram, prompt logs, and download/share buttons for the stories.
3. Support alternate content types (poems, lullabies, interactive choose-your-adventure) with dedicated storyteller prompts and judges.
4. Modularize the code (e.g., separate storyteller/judge modules) so future interfaces like a web UI can reuse the logic cleanly.

---

## Other FAQs
- How long should I spend on this? 
No more than 2-3 hours
- Can I change what the input is? 
Sure
- How long should the story be?
You decide
