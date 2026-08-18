import re

from .markdown import HEADING_RE, mask_fences, restore_fences


def chunk_text(text: str, max_chars: int) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
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


# A chunk that starts mid-section is a fragment nobody can name consistently: the extractor
# sees prose with no idea which part of the syllabus it belongs to, and the same idea comes
# out named differently from two neighbouring chunks. Cutting on headings instead, and
# handing the heading path over with the text, is what lets the naming canon be applied.
# Sections are PACKED up to the budget rather than emitted one per heading, because a
# heavily subdivided document would otherwise multiply the number of model calls.
def chunk_markdown(text: str, max_chars: int) -> list[tuple[str, str]]:
    sections = split_sections(text)
    if not sections:
        return [("", chunk) for chunk in chunk_text(text, max_chars)]

    chunks: list[tuple[str, str]] = []
    buffer: list[str] = []
    paths: list[str] = []

    def flush() -> None:
        if buffer:
            chunks.append((common_path(paths), "\n\n".join(buffer)))
            buffer.clear()
            paths.clear()

    for path, body in sections:
        if len(body) > max_chars:
            flush()
            chunks.extend((path, piece) for piece in chunk_text(body, max_chars))
            continue
        pending = sum(len(b) + 2 for b in buffer)
        if buffer and pending + len(body) > max_chars:
            flush()
        buffer.append(body)
        paths.append(path)
    flush()
    return chunks


def split_sections(text: str) -> list[tuple[str, str]]:
    masked, fences = mask_fences(text)
    stack: list[str] = []
    sections: list[tuple[str, list[str]]] = []
    current: list[str] = []
    path = ""

    def close() -> None:
        if any(line.strip() for line in current):
            sections.append((path, list(current)))
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
        current.append(line)
    close()

    return [
        (p, body)
        for p, lines in sections
        if (body := restore_fences("\n".join(lines), fences).strip())
    ]


def common_path(paths: list[str]) -> str:
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
