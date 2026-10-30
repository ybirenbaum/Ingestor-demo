"""Automate Google NotebookLM's "Audio Overview" feature to turn a block of text
into a ~10 minute AI-hosted podcast episode, and download the resulting audio.

NotebookLM has no public API for this (as of writing), so this drives the real
web UI with Playwright. That makes it inherently fragile: if Google changes the
UI, the locators below may need updating. Run it with `--headed` the first time
to watch it work and fix any selector that no longer matches.

Requires a real, interactive Google account login (NotebookLM is not available
to service accounts / API keys), so this must be run somewhere you can complete
a browser login once -- your own machine, not a headless CI container. The
logged-in session is cached in --profile-dir so you only log in once.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

NOTEBOOKLM_URL = "https://notebooklm.google.com/"
DEFAULT_PROFILE_DIR = Path.home() / ".cache" / "notebooklm-podcast-profile"
LOGIN_TIMEOUT_S = 300
GENERATION_TIMEOUT_S = 15 * 60
POLL_INTERVAL_S = 10


def _ensure_logged_in(page: Page) -> None:
    page.goto(NOTEBOOKLM_URL)
    if "accounts.google.com" in page.url or page.get_by_text("Sign in").count():
        print(
            "Please log in to your Google account in the opened browser window.\n"
            "Waiting up to 5 minutes for you to finish...",
            file=sys.stderr,
        )
        page.wait_for_url(lambda url: "notebooklm.google.com" in url, timeout=LOGIN_TIMEOUT_S * 1000)
        page.wait_for_load_state("networkidle")


def _create_notebook_with_source(page: Page, title: str, text: str) -> None:
    page.goto(NOTEBOOKLM_URL)
    page.wait_for_load_state("networkidle")

    create_btn = page.get_by_role("button", name="Create new").or_(
        page.get_by_role("button", name="New notebook")
    )
    create_btn.first.click()

    # Source picker: choose the "paste text" / "copied text" option rather than
    # uploading a file.
    paste_text_option = page.get_by_text("Copied text").or_(page.get_by_text("Paste text"))
    paste_text_option.first.click()

    textarea = page.locator("textarea").first
    textarea.fill(text)

    insert_btn = page.get_by_role("button", name="Insert")
    insert_btn.click()

    # Wait for the source to finish processing before touching Studio.
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)

    try:
        rename_btn = page.get_by_role("button", name="Untitled notebook")
        rename_btn.click(timeout=3000)
        page.keyboard.press("Control+A")
        page.keyboard.type(title)
        page.keyboard.press("Enter")
    except Exception:
        pass  # Renaming is cosmetic; don't fail the run over it.


def _generate_audio_overview(page: Page, focus_instructions: str, length: str) -> None:
    """Open the Audio Overview customize dialog, set a focus prompt and length, and generate."""
    customize_btn = page.get_by_role("button", name="Customize")
    if customize_btn.count():
        customize_btn.first.click()

        length_option = page.get_by_role("radio", name=length).or_(page.get_by_text(length))
        if length_option.count():
            length_option.first.click()

        focus_box = page.get_by_placeholder("What should the AI hosts focus on?").or_(
            page.locator("textarea").last
        )
        if focus_box.count():
            focus_box.first.fill(focus_instructions)

        generate_btn = page.get_by_role("button", name="Generate")
        generate_btn.first.click()
    else:
        # No customize dialog available in this UI version: fall back to the
        # plain "Generate" button on the Audio Overview card.
        page.get_by_role("button", name="Generate").first.click()


def _wait_for_audio_ready(page: Page) -> None:
    deadline = time.monotonic() + GENERATION_TIMEOUT_S
    while time.monotonic() < deadline:
        if page.get_by_role("button", name="Play").count():
            return
        if page.locator('[aria-label="More"]').count():
            return
        print("Still generating audio overview...", file=sys.stderr)
        page.wait_for_timeout(POLL_INTERVAL_S * 1000)
    raise TimeoutError("Audio overview did not finish generating in time")


def _download_audio(page: Page, output_path: Path) -> None:
    more_menu = page.locator('[aria-label="More"]').first
    more_menu.click()
    with page.expect_download() as download_info:
        page.get_by_text("Download").first.click()
    download = download_info.value
    output_path.parent.mkdir(parents=True, exist_ok=True)
    download.save_as(output_path)


def generate_podcast(
    text: str,
    title: str,
    output_path: Path,
    focus_instructions: str = "Keep this episode to about 10 minutes long.",
    length: str = "Longer",
    profile_dir: Path = DEFAULT_PROFILE_DIR,
    headed: bool = True,
) -> Path:
    """Drive NotebookLM end-to-end: new notebook -> paste text source -> Audio
    Overview, customized for ~10 minutes -> download the finished mp3/wav.

    Returns the path the audio was saved to.
    """
    profile_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        context = pw.chromium.launch_persistent_context(
            str(profile_dir),
            headless=not headed,
            accept_downloads=True,
        )
        try:
            page = context.pages[0] if context.pages else context.new_page()
            _ensure_logged_in(page)
            _create_notebook_with_source(page, title=title, text=text)
            _generate_audio_overview(page, focus_instructions=focus_instructions, length=length)
            _wait_for_audio_ready(page)
            _download_audio(page, output_path)
        finally:
            context.close()

    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("text_file", type=Path, help="Path to a .txt file with the source text")
    parser.add_argument("--title", default="Weekly Parasha Podcast")
    parser.add_argument("--output", type=Path, default=Path("podcast.mp3"))
    parser.add_argument("--length", default="Longer", choices=["Shorter", "Default", "Longer"])
    parser.add_argument(
        "--focus",
        default="Keep this episode to about 10 minutes long.",
        help="Free-text instructions for the AI hosts (NotebookLM's 'focus' field).",
    )
    parser.add_argument("--profile-dir", type=Path, default=DEFAULT_PROFILE_DIR)
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run without a visible browser window (only useful after you've already logged in once).",
    )
    args = parser.parse_args()

    text = args.text_file.read_text(encoding="utf-8")
    output = generate_podcast(
        text=text,
        title=args.title,
        output_path=args.output,
        focus_instructions=args.focus,
        length=args.length,
        profile_dir=args.profile_dir,
        headed=not args.headless,
    )
    print(f"Saved podcast audio to {output}")


if __name__ == "__main__":
    main()
