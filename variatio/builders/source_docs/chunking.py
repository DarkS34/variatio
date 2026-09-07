"""Cutting a document into the pieces one model call is handed."""

import re

from .markdown import HEADING_RE, mask_fences, restore_fences, strip_page_marks


def chunk_markdown(text: str, max_chars: int) -> list[tuple[str, str]]:
    """`chunk_sections` without the per-chunk heading list: `(heading path, body)`."""
    return [(path, body) for path, _headings, body in chunk_sections(text, max_chars)]


def chunk_sections(text: str, max_chars: int) -> list[tuple[str, list[str], str]]:
    """Cut on headings, returning `(heading path, headings, body)` per chunk.

    A chunk that starts mid-section is a fragment nobody can name consistently: the
    extractor sees prose with no idea which part of the syllabus it belongs to, and the same
    idea comes out named differently from two neighbouring chunks. Sections are PACKED up to
    the budget rather than emitted one per heading, or a heavily subdivided document would
    multiply the number of model calls.
    """
    sections = split_sections(text)
    if not sections:
        return [("", [], chunk) for chunk in chunk_text(text, max_chars)]

    chunks: list[tuple[str, list[str], str]] = []
    buffer: list[str] = []
    paths: list[str] = []
    headings: list[str] = []

    def flush() -> None:
        """Close the pending buffer as one chunk."""
        if buffer:
            chunks.append((common_path(paths), list(headings), "\n\n".join(buffer)))
            buffer.clear()
            paths.clear()
            headings.clear()

    for path, heading, body in sections:
        if len(body) > max_chars:
            flush()
            chunks.extend(
                (path, [heading] if index == 0 and heading else [], piece)
                for index, piece in enumerate(chunk_text(body, max_chars))
            )
            continue
        pending = sum(len(b) + 2 for b in buffer)
        if buffer and pending + len(body) > max_chars:
            flush()
        buffer.append(body)
        paths.append(path)
        if heading:
            headings.append(heading)
    flush()
    return chunks


def split_sections(text: str) -> list[tuple[str, str, str]]:
    """Split `text` at its headings into `(heading path, title, body)` sections."""
    masked, fences = mask_fences(strip_page_marks(text))
    stack: list[str] = []
    sections: list[tuple[str, str, list[str]]] = []
    current: list[str] = []
    path = ""
    title = ""

    def close() -> None:
        """Store the lines gathered so far as a section, unless they are all blank."""
        if any(line.strip() for line in current):
            sections.append((path, title, list(current)))
        current.clear()

    for line in masked.splitlines():
        heading = HEADING_RE.match(line)
        if not heading:
            current.append(line)
            continue
        close()
        level = len(heading.group(1))
        del stack[level - 1 :]
        stack.extend([""] * (level - 1 - len(stack)))
        stack.append(heading.group(2).strip())
        path = " > ".join(part for part in stack if part)
        title = stack[-1]
        current.append(line)
    close()

    return [
        (p, t, body)
        for p, t, lines in sections
        if (body := restore_fences("\n".join(lines), fences).strip())
    ]


def chunk_text(text: str, max_chars: int) -> list[str]:
    """Pack the paragraphs of `text` into chunks of at most `max_chars`."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", strip_page_marks(text)) if p.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if current and len(current) + len(paragraph) + 2 > max_chars:
            chunks.append(current)
            current = paragraph
        else:
            current = f"{current}\n\n{paragraph}" if current else paragraph
    if current:
        chunks.append(current)
    return chunks


def common_path(paths: list[str]) -> str:
    """Return the deepest heading path every one of `paths` starts with."""
    parts = [p.split(" > ") for p in paths if p]
    if not parts:
        return ""
    common = parts[0]
    for other in parts[1:]:
        shared: list[str] = []
        for mine, theirs in zip(common, other):
            if mine != theirs:
                break
            shared.append(mine)
        common = shared
        if not common:
            break
    return " > ".join(common)
