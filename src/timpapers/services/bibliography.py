"""BibTeX parsing helpers for the configured-author workflow."""

from __future__ import annotations

from dataclasses import dataclass
import re
from urllib.parse import urlparse


_ACCENT_PATTERN = re.compile(r"""\\['"`^~=.uvHcdbkrt](?:\{)?([A-Za-z])(?:\})?""")
_COMMAND_PATTERN = re.compile(r"\\[A-Za-z]+")
_DOI_PATTERN = re.compile(r"(10\.\d{4,9}/[-._;()/:A-Z0-9]+)", re.IGNORECASE)
_YEAR_PATTERN = re.compile(r"\b(19|20)\d{2}\b")


@dataclass(slots=True)
class BibliographyEntry:
    """Normalized BibTeX entry used as the source of truth for tracked works."""

    key: str
    title: str
    year: int | None
    venue: str | None
    author_list: str
    doi: str | None


def to_raw_bibliography_url(url: str) -> str:
    """Convert common GitHub blob URLs to raw file URLs."""

    parsed = urlparse(url)
    if parsed.netloc != "github.com" or "/blob/" not in parsed.path:
        return url

    path_parts = parsed.path.strip("/").split("/")
    if len(path_parts) < 5:
        return url

    owner, repo, _, ref, *rest = path_parts
    return f"https://raw.githubusercontent.com/{owner}/{repo}/{ref}/{'/'.join(rest)}"


def extract_bibliography_entries(payload: str) -> list[BibliographyEntry]:
    """Parse a BibTeX document into normalized bibliography entries."""

    blocks = _split_bibtex_blocks(payload)
    entries: list[BibliographyEntry] = []
    for block in blocks:
        entry = _parse_block(block)
        if entry is not None:
            entries.append(entry)
    return entries


def _split_bibtex_blocks(payload: str) -> list[str]:
    blocks: list[str] = []
    idx = 0
    while idx < len(payload):
        start = payload.find("@", idx)
        if start == -1:
            break

        brace_start = payload.find("{", start)
        if brace_start == -1:
            break

        depth = 0
        cursor = brace_start
        while cursor < len(payload):
            char = payload[cursor]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    blocks.append(payload[start : cursor + 1])
                    idx = cursor + 1
                    break
            cursor += 1
        else:
            break
    return blocks


def _parse_block(block: str) -> BibliographyEntry | None:
    brace_start = block.find("{")
    if brace_start == -1:
        return None

    body = block[brace_start + 1 : -1].strip()
    key, separator, field_text = body.partition(",")
    if not separator:
        return None

    fields = _parse_fields(field_text)
    title = _clean_bibtex_text(fields.get("title", "Untitled"))
    author_list = _format_authors(fields.get("author", ""))
    year = _parse_year(fields.get("year"))
    venue = _first_nonempty(fields.get("journal"), fields.get("booktitle"), fields.get("publisher"))
    return BibliographyEntry(
        key=key.strip(),
        title=title or "Untitled",
        year=year,
        venue=_clean_bibtex_text(venue) if venue else None,
        author_list=author_list,
        doi=normalize_doi(fields.get("doi")),
    )


def _parse_fields(field_text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    idx = 0
    while idx < len(field_text):
        while idx < len(field_text) and field_text[idx] in " \r\n\t,":
            idx += 1
        if idx >= len(field_text):
            break

        name_start = idx
        while idx < len(field_text) and field_text[idx] not in "=\r\n":
            idx += 1
        name = field_text[name_start:idx].strip().lower()
        if not name:
            break

        while idx < len(field_text) and field_text[idx] != "=":
            idx += 1
        if idx >= len(field_text):
            break
        idx += 1
        while idx < len(field_text) and field_text[idx].isspace():
            idx += 1
        if idx >= len(field_text):
            break

        value, idx = _parse_value(field_text, idx)
        fields[name] = value.strip()
    return fields


def _parse_value(field_text: str, idx: int) -> tuple[str, int]:
    if field_text[idx] == "{":
        return _parse_braced_value(field_text, idx)
    if field_text[idx] == '"':
        return _parse_quoted_value(field_text, idx)

    start = idx
    while idx < len(field_text) and field_text[idx] not in ",\r\n":
        idx += 1
    return field_text[start:idx], idx


def _parse_braced_value(field_text: str, idx: int) -> tuple[str, int]:
    depth = 0
    start = idx + 1
    idx += 1
    while idx < len(field_text):
        char = field_text[idx]
        if char == "{":
            depth += 1
        elif char == "}":
            if depth == 0:
                return field_text[start:idx], idx + 1
            depth -= 1
        idx += 1
    return field_text[start:], idx


def _parse_quoted_value(field_text: str, idx: int) -> tuple[str, int]:
    start = idx + 1
    idx += 1
    escaped = False
    while idx < len(field_text):
        char = field_text[idx]
        if char == '"' and not escaped:
            return field_text[start:idx], idx + 1
        escaped = char == "\\" and not escaped
        if char != "\\":
            escaped = False
        idx += 1
    return field_text[start:], idx


def normalize_doi(value: str | None) -> str | None:
    """Extract and normalize a DOI string when present."""

    if not value:
        return None
    match = _DOI_PATTERN.search(value.strip())
    if match is None:
        return None
    return match.group(1).rstrip(".,;").lower()


def _parse_year(value: str | None) -> int | None:
    if not value:
        return None
    match = _YEAR_PATTERN.search(value)
    if match is None:
        return None
    return int(match.group(0))


def _format_authors(raw_authors: str) -> str:
    parts = [part.strip() for part in raw_authors.split(" and ") if part.strip()]
    return ", ".join(_clean_bibtex_text(part) for part in parts)


def _clean_bibtex_text(value: str) -> str:
    cleaned = value
    cleaned = cleaned.replace("\n", " ")
    cleaned = cleaned.replace("\\&", "&")
    cleaned = cleaned.replace("\\#", "#")
    cleaned = cleaned.replace("\\_", "_")
    cleaned = cleaned.replace("~", " ")
    cleaned = _ACCENT_PATTERN.sub(r"\1", cleaned)
    cleaned = re.sub(r"\\textsuperscript\{([^}]*)\}", r"\1", cleaned)
    cleaned = re.sub(r"\\emph\{([^}]*)\}", r"\1", cleaned)
    cleaned = re.sub(r"\\url\{([^}]*)\}", r"\1", cleaned)
    cleaned = cleaned.replace("{", "").replace("}", "")
    cleaned = _COMMAND_PATTERN.sub("", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _first_nonempty(*values: str | None) -> str | None:
    for value in values:
        if value and value.strip():
            return value
    return None
