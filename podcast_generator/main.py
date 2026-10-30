"""Fetch the current week's parasha and turn it into a ~10 minute NotebookLM podcast.

Usage:
    python -m podcast_generator.main --output parasha_podcast.mp3
"""

from __future__ import annotations

import argparse
from pathlib import Path

from podcast_generator.fetch_parasha import get_parasha_text
from podcast_generator.notebooklm_podcast import DEFAULT_PROFILE_DIR, generate_podcast


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("parasha_podcast.mp3"))
    parser.add_argument("--length", default="Longer", choices=["Shorter", "Default", "Longer"])
    parser.add_argument("--profile-dir", type=Path, default=DEFAULT_PROFILE_DIR)
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()

    parasha = get_parasha_text()
    print(f"Fetched {parasha.name} ({parasha.ref}): {len(parasha.english)} verses")

    generate_podcast(
        text=parasha.combined_text,
        title=f"Parasha {parasha.name}",
        output_path=args.output,
        focus_instructions=(
            f"This is the Torah portion {parasha.name}. Discuss its narrative and "
            "key themes for a general audience. Keep this episode to about 10 "
            "minutes long."
        ),
        length=args.length,
        profile_dir=args.profile_dir,
        headed=not args.headless,
    )
    print(f"Saved podcast audio to {args.output}")


if __name__ == "__main__":
    main()
