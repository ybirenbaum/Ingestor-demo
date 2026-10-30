"""Fetch the text of the current week's Torah portion (parasha) from Sefaria."""

from __future__ import annotations

import dataclasses

import requests

SEFARIA_API = "https://www.sefaria.org/api"


@dataclasses.dataclass
class Parasha:
    name: str
    ref: str
    hebrew: str
    english: str

    @property
    def combined_text(self) -> str:
        """English and Hebrew interleaved verse-by-verse, for feeding to an LLM/TTS pipeline."""
        lines = []
        for i, (he, en) in enumerate(zip(self.hebrew, self.english), start=1):
            lines.append(f"{i}. {en}\n   {he}")
        return "\n".join(lines)


def _flatten(text_field) -> list[str]:
    """Sefaria returns nested lists for multi-chapter refs; flatten to a list of verse strings."""
    if not text_field:
        return []
    if isinstance(text_field, str):
        return [text_field]
    flat: list[str] = []
    for item in text_field:
        flat.extend(_flatten(item))
    return flat


def get_current_parasha_ref() -> tuple[str, str]:
    """Return (display name, Sefaria ref) for this week's Torah portion."""
    resp = requests.get(f"{SEFARIA_API}/calendars", timeout=30)
    resp.raise_for_status()
    data = resp.json()
    for item in data.get("calendar_items", []):
        if item.get("title", {}).get("en") == "Parashat Hashavua":
            return item["displayValue"]["en"], item["ref"]
    raise RuntimeError("Could not find 'Parashat Hashavua' in Sefaria calendars response")


def get_parasha_text(ref: str | None = None) -> Parasha:
    """Fetch the full Hebrew/English text for a parasha ref (defaults to the current week's)."""
    if ref is None:
        name, ref = get_current_parasha_ref()
    else:
        name = ref

    resp = requests.get(
        f"{SEFARIA_API}/texts/{ref}",
        params={"context": 0, "commentary": 0, "pad": 0},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    return Parasha(
        name=name,
        ref=ref,
        hebrew=_flatten(data.get("he")),
        english=_flatten(data.get("text")),
    )


if __name__ == "__main__":
    parasha = get_parasha_text()
    print(f"This week's parasha: {parasha.name} ({parasha.ref})")
    print(f"{len(parasha.english)} verses fetched")
    print(parasha.combined_text[:1000])
