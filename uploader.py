import os
from datetime import datetime

PRIMARY_GAME_URL = "https://www.linkedin.com/games/view/pinpoint/desktop/"
MISSPELLING_KEYWORDS = (
    "linkedin poinpoint answer today",
    "poinpoint answer today",
)

def get_authenticated_service():
    """Authenticates and returns the YouTube service."""
    try:
        import googleapiclient.discovery
        from google.oauth2.credentials import Credentials
    except ImportError as e:
        print(f"Error: Missing YouTube upload dependencies. {e}")
        return None
    
    # We expect these to be set in environment variables (Github Secrets)
    refresh_token = os.environ.get("YOUTUBE_REFRESH_TOKEN")
    client_id = os.environ.get("YOUTUBE_CLIENT_ID")
    client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET")
    
    if not all([refresh_token, client_id, client_secret]):
        print("Error: Missing YouTube OAuth environment variables.")
        return None

    creds = Credentials(
        None, # No access token initially
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret
    )

    return googleapiclient.discovery.build("youtube", "v3", credentials=creds)

def _format_date(date_str):
    if not date_str:
        return "", ""

    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        return date_obj.strftime("%b %d, %Y"), date_obj.strftime("%Y-%m-%d")
    except ValueError:
        return date_str, date_str


def _extract_puzzle_number(data):
    for key in ("puzzleNumber", "puzzle_number", "number", "id", "puzzleId", "puzzle_id"):
        value = data.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _clean_text(value):
    return " ".join(str(value or "").split())


def _build_title(formatted_date, puzzle_number):
    if puzzle_number:
        title = f"LinkedIn Pinpoint Answer Today | Puzzle #{puzzle_number} | {formatted_date} Full Solve"
    else:
        title = f"LinkedIn Pinpoint Answer Today | {formatted_date} | Full Solve & Hints"

    if len(title) <= 100:
        return title

    if puzzle_number:
        return f"LinkedIn Pinpoint Answer Today | #{puzzle_number} | {formatted_date}"
    return f"LinkedIn Pinpoint Answer Today | {formatted_date}"


def _build_tags(formatted_date, iso_date, answer, puzzle_number):
    raw_tags = [
        "LinkedIn Pinpoint Answer Today",
        "Pinpoint Answer Today",
        "LinkedIn Pinpoint",
        *MISSPELLING_KEYWORDS,
        "LinkedIn Pinpoint Answer",
        "LinkedIn Pinpoint Hints Today",
        "Pinpoint Hints Today",
        "Pinpoint Today",
        "Pinpoint Answer",
        "linkedin pinpoint today",
    ]

    if formatted_date:
        raw_tags.extend(
            [
                f"LinkedIn Pinpoint {formatted_date}",
                f"Pinpoint Answer {formatted_date}",
            ]
        )

    if iso_date:
        raw_tags.append(f"LinkedIn Pinpoint {iso_date}")

    if puzzle_number:
        raw_tags.extend(
            [
                f"LinkedIn Pinpoint #{puzzle_number}",
                f"Pinpoint #{puzzle_number} answer",
            ]
        )

    if answer:
        raw_tags.extend(
            [
                f"LinkedIn Pinpoint {answer}",
                f"Pinpoint answer {answer}",
            ]
        )

    raw_tags.extend(
        [
            "LinkedIn Games",
            "Pinpoint Game",
            "Daily Puzzle",
            "Word Association Game",
        ]
    )

    tags = []
    seen = set()
    total_chars = 0

    for tag in raw_tags:
        cleaned = _clean_text(tag)
        lowered = cleaned.lower()
        if not cleaned or lowered in seen:
            continue

        projected_total = total_chars + len(cleaned)
        if tags:
            projected_total += 1
        if projected_total > 480:
            continue

        tags.append(cleaned)
        seen.add(lowered)
        total_chars = projected_total

    return tags


def build_video_metadata(data):
    """
    Builds keyword-focused YouTube metadata for daily LinkedIn Pinpoint videos.
    """
    date_str = _clean_text(data.get("date"))
    answer = _clean_text(data.get("answer"))
    raw_clues = data.get("clues", [])
    if not isinstance(raw_clues, (list, tuple)):
        raw_clues = [raw_clues]
    clues = [_clean_text(clue) for clue in raw_clues if _clean_text(clue)]
    puzzle_number = _extract_puzzle_number(data)
    formatted_date, iso_date = _format_date(date_str)

    title = _build_title(formatted_date or date_str or "Today", puzzle_number)
    tags = _build_tags(formatted_date, iso_date, answer, puzzle_number)

    description_lines = [
        f"LinkedIn Pinpoint Answer Today for {formatted_date or date_str or 'today'}.",
        "This Pinpoint answer today video covers the clues, human-like guesses, hints, and the full LinkedIn Pinpoint solve.",
        "",
    ]

    if puzzle_number:
        description_lines.append(f"Puzzle: #{puzzle_number}")
    if iso_date:
        description_lines.append(f"Date: {formatted_date} ({iso_date})")
    elif formatted_date:
        description_lines.append(f"Date: {formatted_date}")

    if clues:
        description_lines.append(f"Today's clues: {', '.join(clues)}")

    description_lines.extend(
        [
            "",
            "Play LinkedIn Pinpoint:",
            PRIMARY_GAME_URL,
            "",
            "More Pinpoint answers:",
            "https://pinpointanswertoday.online/today",
            "Pinpoint archive:",
            "https://pinpointanswertoday.online/archive",
        ]
    )

    if answer:
        description_lines.extend(
            [
                "",
                f"Final category in this solve: {answer}",
            ]
        )

    description_lines.extend(
        [
            "",
            "#LinkedInPinpoint #PinpointAnswerToday #PinpointHints",
        ]
    )

    return {
        "title": title,
        "description": "\n".join(description_lines).strip(),
        "tags": tags,
    }


def upload_video(video_path, data, metadata=None):
    """
    Uploads the video to YouTube with SEO metadata.
    data format expected: { "date": "YYYY-MM-DD", "answer": "..." }
    """
    youtube = get_authenticated_service()
    if not youtube:
        return False

    try:
        from googleapiclient.http import MediaFileUpload
    except ImportError as e:
        print(f"Error: Missing YouTube upload dependencies. {e}")
        return False

    metadata = metadata or build_video_metadata(data)

    body = {
        "snippet": {
            "title": metadata["title"],
            "description": metadata["description"],
            "tags": metadata["tags"],
            "categoryId": "20",
            "defaultLanguage": "en",
            "defaultAudioLanguage": "en",
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False
        }
    }

    try:
        print(f"SEO Title: {metadata['title']}")
        print(f"SEO Tags: {metadata['tags']}")
        print(f"Uploading {video_path}...")
        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=MediaFileUpload(video_path, chunksize=-1, resumable=True)
        )
        response = request.execute()
        print(f"Upload Successful! Video ID: {response['id']}")
        return True
    except Exception as e:
        status = getattr(getattr(e, "resp", None), "status", "unknown")
        content = getattr(e, "content", str(e))
        print(f"Upload failed with status {status}:\n{content}")
        return False
