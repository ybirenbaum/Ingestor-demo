# Parasha Podcast Generator

Fetches the current week's Torah portion (parasha) text from [Sefaria](https://www.sefaria.org)
and uses Google NotebookLM's "Audio Overview" feature to turn it into a ~10
minute, two-host podcast episode.

## Important limitations

- **NotebookLM has no public API.** This drives the real notebooklm.google.com
  web UI with [Playwright](https://playwright.dev/), so it's inherently more
  fragile than a normal API integration -- if Google changes the UI, the
  selectors in `notebooklm_podcast.py` may need small updates.
- **You must run this somewhere you can complete an interactive Google login**
  (your own machine, not a headless server/CI). NotebookLM requires a real
  Google account session; there's no service-account or API-key auth path for
  it. The first run opens a visible browser window for you to log in; that
  session is cached in `--profile-dir` (default `~/.cache/notebooklm-podcast-profile`)
  so subsequent runs can reuse it with `--headless`.
- **Episode length isn't exactly configurable.** NotebookLM's Audio Overview
  customize dialog offers Shorter / Default / Longer length presets plus a
  free-text "focus" instruction, not a precise minute count. This script picks
  `Longer` by default and adds "keep this to about 10 minutes" as a focus
  instruction, which gets you close but isn't guaranteed exact.

## Setup

```bash
pip install -r podcast_generator/requirements.txt
playwright install chromium
```

## Usage

```bash
python -m podcast_generator.main --output parasha_podcast.mp3
```

On first run, a browser window opens -- log in to Google when prompted. The
script then creates a new NotebookLM notebook, pastes in this week's parasha
text as a source, requests a ~10 minute Audio Overview, waits for it to
generate (can take several minutes), and downloads the resulting audio file.

### Using your own text instead of fetching from Sefaria

```bash
python -m podcast_generator.notebooklm_podcast my_text.txt --output episode.mp3
```
