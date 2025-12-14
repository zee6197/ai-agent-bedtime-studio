import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from openai import APIConnectionError, APIError, OpenAI, RateLimitError

"""
Before submitting the assignment, describe here in a few sentences what you would have built next if you spent 2 more hours on this project:

- Build a light web UI so kids/parents can see the diagram and story without using the CLI
- Create a small library of reusable prompt modules for alternative story structures (song, poem, adventure quest)
- Cache judge feedback and sampled stories so we can run quick offline evaluations without repeatedly calling the API

"""


STORYTELLER_SYSTEM_PROMPT = (
    "You are a thoughtful bedtime storyteller writing for ages five to ten. "
    "Favor concrete imagery, uplifting arcs, gentle suspense, and a positive resolution. "
    "Keep vocabulary accessible to early readers while still sounding magical."
)

JUDGE_SYSTEM_PROMPT = (
    "You are a meticulous children's literature critic. "
    "Assess safety, age-appropriateness, structure, creativity, and fidelity to the request. "
    "Respond with JSON only."
)

LENGTH_OPTIONS = {
    "short": 220,
    "medium": 380,
    "long": 520,
}


@dataclass
class Config:
    storyteller_temp: float = 0.65
    judge_temp: float = 0.2
    max_attempts: int = 2
    api_retries: int = 3
    api_timeout: int = 30
    token_warn_threshold: int = 3500
    log_path: str = "story_sessions.log"

    @classmethod
    def from_env(cls) -> "Config":
        def _float(name: str, default: float) -> float:
            raw = os.getenv(name)
            if not raw:
                return default
            try:
                return float(raw)
            except ValueError:
                print(f"Warning: could not parse {name}, using default {default}.")
                return default

        def _int(name: str, default: int) -> int:
            raw = os.getenv(name)
            if not raw:
                return default
            try:
                return max(1, int(raw))
            except ValueError:
                print(f"Warning: could not parse {name}, using default {default}.")
                return default

        return cls(
            storyteller_temp=_float("STORY_TEMP", cls.storyteller_temp),
            judge_temp=_float("JUDGE_TEMP", cls.judge_temp),
            max_attempts=_int("MAX_STORY_ATTEMPTS", cls.max_attempts),
            api_retries=_int("API_RETRIES", cls.api_retries),
            api_timeout=_int("API_TIMEOUT_SECONDS", cls.api_timeout),
            token_warn_threshold=_int("TOKEN_WARN_THRESHOLD", cls.token_warn_threshold),
            log_path=os.getenv("STORY_LOG_PATH", cls.log_path),
        )


CONFIG = Config.from_env()
_CLIENT: Optional[OpenAI] = None
LOG_FILE = Path(CONFIG.log_path)


class UserExit(Exception):
    """Raised when the user elects to exit the CLI."""


def _log_event(event: Dict[str, object]) -> None:
    """Append structured event to a log file for debugging and traceability."""

    try:
        if LOG_FILE.parent and not LOG_FILE.parent.exists():
            LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event) + "\n")
    except OSError:
        pass  # Logging should never break the CLI


@dataclass
class StoryRequest:
    """Settings collected from the user that define the desired story."""

    description: str
    characters: str
    tone: str
    lesson: str
    length_label: str

    @property
    def target_words(self) -> int:
        return LENGTH_OPTIONS.get(self.length_label, LENGTH_OPTIONS["medium"])


@dataclass
class StoryOutcome:
    """Container for the final story and the judge's assessment."""

    story: str
    judge_report: Dict[str, object]
    approved: bool


def _prompt_with_validation(prompt: str, default: str) -> Optional[str]:
    """Collect user input and guard against empty or low-signal answers."""

    while True:
        raw = input(prompt).strip()
        if not raw:
            return default
        if raw.lower() == "cancel":
            return None
        if raw.lower() == "exit":
            raise UserExit()
        if _looks_like_noise(raw):
            print("That doesn't look like a story-friendly answer. Please try again or press enter for the default.")
            continue
        return raw


def _looks_like_noise(text: str) -> bool:
    """Detect numeric or low-information strings."""

    if len(text) < 3:
        return True
    alpha_chars = [ch for ch in text if ch.isalpha()]
    alpha_count = len(alpha_chars)
    if alpha_count == 0:
        return True
    if alpha_count < max(3, len(text) // 3):
        return True
    vowels = set("aeiouAEIOU")
    if not any(ch in vowels for ch in text):
        return True
    unique_chars = set(alpha_chars)
    if len(unique_chars) <= 2:
        return True
    normalized = "".join(ch.lower() for ch in alpha_chars)
    if " " not in text and len(normalized) >= 6:
        unique_vowels = {ch for ch in normalized if ch in vowels}
        if len(unique_vowels) < 2:
            return True
        half = len(normalized) // 2
        if normalized[:half] == normalized[half:]:
            return True
        return True
    return False


def _estimate_tokens(text: str) -> int:
    """Rough token estimate assuming 0.75 words per token."""

    words = len(text.split())
    return max(1, int(words / 0.75))


def _maybe_warn_token_budget(*segments: str) -> None:
    approx_tokens = sum(_estimate_tokens(seg) for seg in segments)
    if approx_tokens > CONFIG.token_warn_threshold:
        print(
            f"Warning: this request may exceed the token budget "
            f"({approx_tokens} estimated tokens > {CONFIG.token_warn_threshold})."
        )


def _get_client() -> OpenAI:
    global _CLIENT
    if _CLIENT is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY environment variable is not set.")
        _CLIENT = OpenAI(api_key=api_key)
    return _CLIENT


def call_model(messages: List[Dict[str, str]], max_tokens: int = 800, temperature: float = 0.7) -> str:
    """Wrapper around OpenAI chat completion API."""

    client = _get_client()
    last_error: Optional[Exception] = None
    for attempt in range(1, CONFIG.api_retries + 1):
        try:
            resp = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                timeout=CONFIG.api_timeout,
            )
            content = resp.choices[0].message.content  # type: ignore
            _log_event(
                {
                    "type": "chat_completion",
                    "attempt": attempt,
                    "messages": messages,
                    "response_preview": content[:200],
                }
            )
            return content
        except (APIConnectionError, RateLimitError, APIError) as exc:  # pragma: no cover - network call
            last_error = exc
            _log_event(
                {
                    "type": "chat_error",
                    "attempt": attempt,
                    "error": str(exc),
                }
            )
            if attempt < CONFIG.api_retries:
                sleep_for = min(2 ** (attempt - 1), 5)
                time.sleep(sleep_for)
    raise RuntimeError("OpenAI API call failed after multiple attempts.") from last_error


def collect_story_preferences(depth: int = 0) -> StoryRequest:
    """Prompt the user for storytelling preferences with friendly defaults."""

    print("Let's gather a few details so I can craft the perfect bedtime story. Type 'cancel' to restart or 'exit' to quit.")
    description = _prompt_with_validation(
        "What is the main idea or request for the story? ", "A cozy adventure featuring loyal friends."
    )
    if description is None:
        return collect_story_preferences()
    characters = _prompt_with_validation(
        "Any key characters or creatures to include? ", "A curious child and their playful pet."
    )
    if characters is None:
        return collect_story_preferences()
    tone = _prompt_with_validation(
        "Desired tone (e.g., silly, gentle, adventurous)? ", "Gentle and hopeful"
    )
    if tone is None:
        return collect_story_preferences()
    lesson = _prompt_with_validation(
        "Is there a lesson or theme to emphasize? ", "Friendship and kindness matter."
    )
    if lesson is None:
        return collect_story_preferences()
    length_label = input("Preferred length (short/medium/long)? ").strip().lower() or "medium"
    if length_label == "cancel":
        print("Restarting preference collection...\n")
        return collect_story_preferences()
    if length_label not in LENGTH_OPTIONS:
        print("Unrecognized length, defaulting to medium.")
        length_label = "medium"
    return StoryRequest(description, characters, tone, lesson, length_label)


def summarize_request(req: StoryRequest) -> str:
    """Generate a concise summary passed into the storyteller and judge."""

    return (
        f"Story idea: {req.description}. Characters: {req.characters}. "
        f"Tone: {req.tone}. Lesson: {req.lesson}. Target length: {req.length_label} (~{req.target_words} words)."
    )


def build_story(req: StoryRequest, summary: str, critique: Optional[str] = None) -> str:
    """Call the storyteller model with structured prompts and optional critique."""

    critique = critique or "None. Focus on delighting the child audience."
    user_prompt = f"""
You will write a single bedtime story.

REQUEST SUMMARY:
{summary}

CRITIQUE TO ADDRESS (if any):
{critique}

CONSTRAINTS:
- Keep the total length close to {req.target_words} words.
- Use simple paragraphs with vivid sensory details.
- Include a clear beginning, middle, and end plus a gentle twist or surprise.
- Close with a short moral sentence explicitly tagged as "Moral:".

RESPONSE FORMAT:
Title: <captivating title>
Story:
<one or more short paragraphs>
Moral: <one sentence moral>
"""
    _maybe_warn_token_budget(summary, critique, user_prompt)
    messages = [
        {"role": "system", "content": STORYTELLER_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt.strip()},
    ]
    return call_model(messages, max_tokens=900, temperature=CONFIG.storyteller_temp)


def judge_story(story: str, summary: str) -> Dict[str, object]:
    """Ask the judge model for a JSON critique of the story."""

    judge_prompt = f"""
Evaluate the following story for a bedtime audience ages five to ten.

USER REQUEST SUMMARY:
{summary}

STORY TO REVIEW:
{story}

Return strict JSON with keys:
verdict: "approve" or "revise".
summary: one-sentence assessment.
issues: array of concrete problems, empty array if none.
suggestions: array of actionable improvements aimed at the storyteller.
"""
    _maybe_warn_token_budget(summary, story, judge_prompt)
    messages = [
        {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
        {"role": "user", "content": judge_prompt.strip()},
    ]
    raw_response = call_model(messages, max_tokens=400, temperature=CONFIG.judge_temp)
    return _normalize_judge_report(_parse_judge_response(raw_response))


def _parse_judge_response(raw: str) -> Dict[str, object]:
    """Best-effort JSON parsing that strips Markdown fences."""

    cleaned = raw.strip().strip("`")
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    target = match.group(0) if match else cleaned
    try:
        return json.loads(target)
    except json.JSONDecodeError:
        return {
            "verdict": "revise",
            "summary": "Judge response was unreadable; request revision for safety.",
            "issues": ["Malformed JSON from judge."],
            "suggestions": [cleaned],
        }


def _normalize_judge_report(report: Dict[str, object]) -> Dict[str, object]:
    """Ensure judge report fields are present and well-typed."""

    verdict = str(report.get("verdict", "revise")).lower()
    if verdict not in {"approve", "revise"}:
        verdict = "revise"
    summary = str(report.get("summary") or "No summary provided.")
    issues = report.get("issues") or []
    suggestions = report.get("suggestions") or []
    if not isinstance(issues, list):
        issues = [str(issues)]
    if not isinstance(suggestions, list):
        suggestions = [str(suggestions)]
    normalized = {
        "verdict": verdict,
        "summary": summary,
        "issues": [str(item) for item in issues],
        "suggestions": [str(item) for item in suggestions],
    }
    return normalized


def craft_story_with_feedback(req: StoryRequest, summary: str, max_attempts: Optional[int] = None) -> StoryOutcome:
    """Iteratively generate stories until the judge approves or attempts are exhausted."""

    max_attempts = max_attempts or CONFIG.max_attempts
    critique: Optional[str] = None
    final_story = ""
    judge_report: Dict[str, object] = {}
    approved = False
    for attempt in range(1, max_attempts + 2):
        print(f"\nGenerating story draft #{attempt}...")
        final_story = build_story(req, summary, critique)
        judge_report = judge_story(final_story, summary)
        verdict = str(judge_report.get("verdict", "revise")).lower()
        print(f"Judge verdict: {verdict.upper()} — {judge_report.get('summary')}")
        if verdict == "approve":
            approved = True
            break
        suggestions = judge_report.get("suggestions", []) or []
        issues = judge_report.get("issues", []) or []
        critique_lines = []
        if issues:
            critique_lines.append("Issues to fix:\n- " + "\n- ".join(issues))
        if suggestions:
            critique_lines.append("Suggestions:\n- " + "\n- ".join(suggestions))
        critique = "\n\n".join(critique_lines) or "Please refine pacing and clarity."
    return StoryOutcome(final_story, judge_report, approved)


def offer_user_revision(story: str, req: StoryRequest, summary: str) -> str:
    """Give the user a chance to nudge the story after judge approval."""

    print("\nWould you like any quick adjustments? Examples: 'make it shorter', 'change the ending', 'more dialogue'.")
    tweak = input("Enter optional tweak instructions (press enter to keep as-is): ")
    if not tweak.strip():
        return story
    print("Creating revised version with your feedback...")
    critique = f"User feedback: {tweak.strip()}. Preserve the best parts of the prior story when possible."
    return build_story(req, summary, critique)


def handle_unapproved_story(
    req: StoryRequest, summary: str, outcome: StoryOutcome
) -> Tuple[StoryOutcome, bool]:
    """Offer recovery options when the judge continues to request revisions."""

    print("\nThe judge still has concerns after several attempts.")
    issues = outcome.judge_report.get("issues", [])
    suggestions = outcome.judge_report.get("suggestions", [])
    if issues:
        print("Judge issues:")
        for issue in issues:
            print(f"- {issue}")
    if suggestions:
        print("Judge suggestions:")
        for tip in suggestions:
            print(f"- {tip}")

    prompt = (
        "Enter new gentle guidance to try another revision, type 'restart' to re-enter your preferences, "
        "or press enter to accept the current draft: "
    )
    print()
    user_input = input(prompt).strip()
    if not user_input:
        return outcome, False
    if user_input.lower() == "restart":
        print("Restarting preference collection...")
        return outcome, True

    extra_guidance = user_input
    critique = (
        "Judge concerns:\n- "
        + "\n- ".join(str(item) for item in issues or suggestions or ["Tone too intense."])
        + f"\n\nUser guidance:\n{extra_guidance}"
    )
    print("\nGenerating an additional draft with your guidance...")
    new_story = build_story(req, summary, critique)
    new_report = judge_story(new_story, summary)
    new_verdict = str(new_report.get("verdict", "revise")).lower()
    print(f"Judge verdict after manual guidance: {new_verdict.upper()} — {new_report.get('summary')}")
    return StoryOutcome(new_story, new_report, new_verdict == "approve"), False


def run_cli() -> None:
    """Primary CLI runner that wires together user input, storyteller, and judge."""

    print("Welcome to the Bedtime Story Studio!")
    print(
        f"Config — Story temp: {CONFIG.storyteller_temp}, "
        f"Judge temp: {CONFIG.judge_temp}, Attempts: {CONFIG.max_attempts}"
    )
    while True:
        req = collect_story_preferences()
        summary = summarize_request(req)
        print(f"\nGreat! Here's how I understand your request:\n{summary}")
        try:
            outcome = craft_story_with_feedback(req, summary)
        except RuntimeError as err:
            retry = input(f"\nEncountered an issue ({err}). Try again? (y/n): ").strip().lower()
            if retry == "y":
                continue
            raise
        if not outcome.approved:
            outcome, restart = handle_unapproved_story(req, summary, outcome)
            if restart:
                continue
        story = offer_user_revision(outcome.story, req, summary)
        break
    print("\n—— Final Bedtime Story ——")
    print(story)
    print("\nJudge summary:")
    print(json.dumps(outcome.judge_report, indent=2))


def validate_environment() -> None:
    """Ensure required environment variables and paths are sane before prompting."""

    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY environment variable is not set.")
    try:
        if LOG_FILE.exists():
            LOG_FILE.touch(exist_ok=True)
    except OSError:
        print("Warning: cannot write to log file path; logging disabled.")


if __name__ == "__main__":
    try:
        validate_environment()
        run_cli()
    except KeyboardInterrupt:  # pragma: no cover - CLI nicety
        print("\nGoodnight! Story creation cancelled.")
    except UserExit:
        print("\nGoodnight! See you next story time.")
    except RuntimeError as err:
        print(f"\nSorry, something went wrong: {err}")
