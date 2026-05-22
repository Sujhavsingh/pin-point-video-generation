import requests
import os
import json
import random
import re
from difflib import SequenceMatcher

WORKER_URL = "https://linkedin-pinpoint-worker.gdgdughdshf.workers.dev/today/BloggingIo@7"

def fetch_daily_data():
    """Fetches the daily Pinpoint answer and clues."""
    try:
        response = requests.get(WORKER_URL, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get("success"):
            return data["data"]
        else:
            print("API returned success=False")
            return None
    except Exception as e:
        print(f"Error fetching daily data: {e}")
        return None

def _normalize_phrase(value):
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _sanitize_guess(value):
    cleaned = str(value or "").strip().strip("\"'`")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned[:80]


def _is_too_close_to_answer(guess, correct_answer):
    normalized_guess = _normalize_phrase(guess)
    normalized_answer = _normalize_phrase(correct_answer)

    if not normalized_guess or not normalized_answer:
        return False

    if normalized_guess == normalized_answer:
        return True

    if normalized_guess in normalized_answer or normalized_answer in normalized_guess:
        return True

    guess_tokens = set(normalized_guess.split())
    answer_tokens = set(normalized_answer.split())
    if guess_tokens and answer_tokens and guess_tokens.intersection(answer_tokens):
        return True

    return SequenceMatcher(None, normalized_guess, normalized_answer).ratio() >= 0.72


def _select_guess(candidates, correct_answer, used_guesses):
    for candidate in candidates:
        cleaned = _sanitize_guess(candidate)
        normalized = _normalize_phrase(cleaned)

        if not cleaned or normalized in used_guesses:
            continue
        if _is_too_close_to_answer(cleaned, correct_answer):
            continue

        used_guesses.add(normalized)
        return cleaned

    return ""


def _fallback_domains():
    return {
        "animals": {
            "keywords": {"barn", "snowy", "screech", "horned", "hoot", "beak", "claw", "wing", "tail", "fur", "owl"},
            "guesses": ["animals", "birds", "wildlife"],
        },
        "food": {
            "keywords": {"butter", "chicken", "paneer", "grape", "cookie", "corn", "ginger", "salmon", "sweet", "bread"},
            "guesses": ["foods", "ingredients", "dishes"],
        },
        "technology": {
            "keywords": {"thermal", "laser", "3d", "inkjet", "matrix", "software", "digital", "server", "printer", "app"},
            "guesses": ["technology", "electronics", "gadgets"],
        },
        "places": {
            "keywords": {"brazil", "rio", "manaus", "paulo", "capital", "river", "island", "mountain", "desert", "ocean"},
            "guesses": ["countries", "cities", "places"],
        },
        "sports": {
            "keywords": {"arsenal", "juventus", "madrid", "united", "goal", "tennis", "golf", "soccer", "hockey"},
            "guesses": ["sports", "teams", "athletes"],
        },
        "office": {
            "keywords": {"calendar", "stapler", "paperweight", "mouse", "office", "desk", "meeting", "resume", "linkedin"},
            "guesses": ["office items", "work tools", "business"],
        },
        "arts": {
            "keywords": {"mona", "vitruvian", "album", "song", "movie", "theater", "novel", "painting", "music"},
            "guesses": ["art", "movies", "music terms"],
        },
        "science": {
            "keywords": {"ionic", "genetic", "metric", "mass", "storm", "thunder", "hail", "electric", "space", "atom"},
            "guesses": ["science", "chemistry", "weather"],
        },
        "travel": {
            "keywords": {"airport", "subway", "rail", "helmet", "sandals", "handbag", "luggage", "flight", "hotel"},
            "guesses": ["travel", "transportation", "vehicles"],
        },
    }


def _fallback_guess(visible_clues, used_guesses, correct_answer):
    normalized_clues = _normalize_phrase(" ".join(str(clue) for clue in visible_clues))
    scored_domains = []

    for domain in _fallback_domains().values():
        score = sum(1 for keyword in domain["keywords"] if keyword in normalized_clues)
        if score:
            scored_domains.append((score, domain["guesses"]))

    scored_domains.sort(key=lambda item: item[0], reverse=True)

    candidates = []
    for _, guesses in scored_domains:
        candidates.extend(guesses)

    generic_pool = [
        "technology",
        "animals",
        "foods",
        "brands",
        "countries",
        "sports",
        "office items",
        "music terms",
        "travel",
        "plants",
    ]
    random.shuffle(generic_pool)
    candidates.extend(generic_pool)

    return _select_guess(candidates, correct_answer, used_guesses) or "things"


def _extract_json_array(text):
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1]
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("\n", 1)[0]

    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start == -1 or end == -1 or end < start:
        return []

    try:
        parsed = json.loads(cleaned[start : end + 1])
        if isinstance(parsed, list):
            return parsed
    except json.JSONDecodeError:
        return []

    return []


def _build_stage_prompt(visible_clues, correct_answer, stage_number):
    clue_list = ", ".join(visible_clues)
    return f"""
You are scripting a realistic LinkedIn Pinpoint gameplay recording.

Visible clues right now: {clue_list}
Correct final category: "{correct_answer}"
Stage number: {stage_number}

Generate 4 guesses that a normal human player might type at this point before seeing more clues.

Rules:
- Every guess must be wrong.
- Do not use the correct answer or a near-synonym.
- Prefer broad, slightly mistaken, or imperfect categories over polished expert answers.
- Keep each guess to 1-4 words.
- Avoid repeating the same core noun as the correct answer.
- If only one clue is visible, make the guesses noticeably tentative.

Return ONLY a JSON array of strings.
"""


def generate_plausible_guesses(clues, correct_answer):
    """
    Uses Gemini to generate stage-by-stage incorrect guesses that feel human.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    used_guesses = set()
    planned_guesses = []
    clue_list = clues if isinstance(clues, (list, tuple)) else [clues]
    stage_clues = [
        clue_list[:1],
        clue_list[:2],
    ]

    model = None
    if api_key:
        try:
            import google.generativeai as genai

            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-3-flash-preview")
        except Exception as e:
            print(f"Warning: Gemini client unavailable, using fallback guesses. {e}")
    else:
        print("Warning: GEMINI_API_KEY not found. Using fallback human-like guesses.")

    for stage_number, visible_clues in enumerate(stage_clues, start=1):
        if not visible_clues:
            continue

        chosen_guess = ""

        if model is not None:
            prompt = _build_stage_prompt(visible_clues, correct_answer, stage_number)
            try:
                response = model.generate_content(prompt)
                candidates = _extract_json_array(response.text)
                chosen_guess = _select_guess(candidates, correct_answer, used_guesses)
            except Exception as e:
                print(f"Warning: Gemini stage {stage_number} guess failed. {e}")

        if not chosen_guess:
            chosen_guess = _fallback_guess(visible_clues, used_guesses, correct_answer)

        planned_guesses.append(chosen_guess)

    return planned_guesses[:2]
