import time
import random
from playwright.sync_api import sync_playwright, Page

GAME_URL = "https://www.linkedin.com/games/view/pinpoint/desktop/"

def human_type(page: Page, selector: str, text: str, allow_typo=False):
    """Types text with random delays between keystrokes."""
    page.focus(selector)
    typo_index = -1
    if allow_typo and len(text) > 4 and random.random() < 0.35:
        typo_index = random.randint(1, len(text) - 2)

    for index, char in enumerate(text):
        if index == typo_index and char.isalpha():
            wrong_char = random.choice("abcdefghijklmnopqrstuvwxyz")
            if wrong_char == char.lower():
                wrong_char = "e"
            page.keyboard.type(wrong_char)
            time.sleep(random.uniform(0.04, 0.09))
            page.keyboard.press("Backspace")
            time.sleep(random.uniform(0.05, 0.12))

        page.keyboard.type(char)
        if char == " ":
            time.sleep(random.uniform(0.08, 0.18))
        else:
            time.sleep(random.uniform(0.05, 0.16))

def human_delay(min_seconds=2, max_seconds=5):
    """Random pause to simulate thinking."""
    time.sleep(random.uniform(min_seconds, max_seconds))

def study_visible_clues(page: Page):
    """Hovers over visible clue cards with short pauses to mimic reading."""
    clue_cards = page.locator(".pinpoint__card--clue")

    try:
        count = min(clue_cards.count(), 5)
    except Exception:
        return

    for index in range(count):
        card = clue_cards.nth(index)
        try:
            if not card.is_visible():
                continue
            box = card.bounding_box()
            if box:
                x = box["x"] + (box["width"] * random.uniform(0.25, 0.75))
                y = box["y"] + (box["height"] * random.uniform(0.3, 0.7))
                page.mouse.move(x, y, steps=random.randint(8, 18))
            card.hover()
            time.sleep(random.uniform(0.25, 0.8))
        except Exception:
            continue


def clear_input(page: Page, selector: str):
    page.click(selector)
    page.keyboard.press("Control+A")
    time.sleep(random.uniform(0.05, 0.12))
    page.keyboard.press("Backspace")
    time.sleep(random.uniform(0.08, 0.18))


def play_pinpoint(data, output_video_path):
    """
    Plays the Pinpoint game using Playwright.
    Records the session to output_video_path.
    """
    answer = data["answer"]
    
    # We will receive guesses from the main loop logic, 
    # but strictly this function just executes the actions.
    # For simplicity, we'll take guesses as an argument or logic inside.
    # Let's import correct logic here or pass it in. 
    # To keep signatures clean, let's pass a list of guesses to try before the real one.
    
    guesses_to_try = data.get("plausible_guesses", [])
    
    with sync_playwright() as p:
        # Launch options for stealth and video
        browser = p.chromium.launch(
            headless=False, # Must be headless=False to actually record properly usually, or use xvfb on CI
            args=[
                "--disable-blink-features=AutomationControlled",
                "--start-maximized",
                "--no-sandbox"
            ]
        )
        
        # Context with video recording
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            record_video_dir=".", # We'll move it later
            record_video_size={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="en-US",
            timezone_id="Asia/Kolkata" # User asked for Indian context logic, though mostly for Date. Browser location helps too.
        )
        
        # Stealth scripts
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        page = context.new_page()
        
        try:
            print(f"Navigating to {GAME_URL}...")
            page.goto(GAME_URL, wait_until="domcontentloaded")
            human_delay(3, 5)

            # Specific Start Button Selector provided by user
            start_btn_selector = "#launch-footer-start-button"
            
            try:
                # Wait for the start button to be visible
                print("Waiting for start button...")
                page.wait_for_selector(start_btn_selector, timeout=10000)
                page.locator(start_btn_selector).click()
                print("Clicked Start Game.")
                human_delay(2, 4)
            except Exception as e:
                print(f"Start button interaction failed or skipped: {e}")

            # The game interface input field
            input_selector = "input.pinpoint__input"
            
            # Wait for the first clue to ensure game started
            try:
                page.wait_for_selector(".pinpoint__card--clue", timeout=10000)
                print("First clue visible.")
            except:
                print("Warning: Clue card not found immediately.")

            # Attempt 1-2: Wrong guesses
            for i, guess in enumerate(guesses_to_try):
                print(f"Typing plausible guess {i+1}: {guess}")
                try:
                    page.wait_for_selector(input_selector, state="visible", timeout=10000)
                    study_visible_clues(page)
                    human_delay(1.5, 3.5)
                    clear_input(page, input_selector)
                    human_type(page, input_selector, guess, allow_typo=True)
                    human_delay(0.7, 1.8)
                    page.keyboard.press("Enter")
                    human_delay(3, 5)
                except Exception as e:
                    print(f"Could not enter guess '{guess}': {e}")
            
            # Final Attempt: Correct Answer
            print(f"Typing correct answer: {answer}")
            try:
                page.wait_for_selector(input_selector, state="visible", timeout=10000)
                study_visible_clues(page)
                human_delay(2.5, 4.5)
                clear_input(page, input_selector)
                human_type(page, input_selector, answer, allow_typo=False)
                human_delay(0.5, 1.5)
                page.keyboard.press("Enter")
                
                # Wait for Win Screen
                human_delay(5, 8) 
                print("Finished gameplay.")
            except Exception as e:
                print(f"Error entering correct answer: {e}")

        except Exception as e:
            print(f"Error during gameplay: {e}")
        finally:
            context.close() # Saves the video
            browser.close()
            
            # Rename the video file to the expected output path
            # context.close() saves the video to a random name in record_video_dir
            # We need to find it and rename it.
            import os
            import shutil
            
            # Find the latest .webm file (Playwright records to webm)
            # We filter for files modified in the last minute to avoid picking old ones
            # But simple max time is usually fine in ephemeral environments
            files = [f for f in os.listdir(".") if f.endswith(".webm")]
            if files:
                latest_video = max(files, key=os.path.getctime)
                shutil.move(latest_video, output_video_path)
                print(f"Video saved to {output_video_path}")
            else:
                print("No video file found.")

# Usage example (commented out)
# play_pinpoint({"answer": "Apple", "plausible_guesses": ["Fruit", "Red"]}, "output.webm")
