"""The transcription of each picture, cached by the picture's own content and shared by every
document of the workspace.
"""

import json
from pathlib import Path

from loguru import logger

from ... import config
from ...core import inference
from ...core.json_io import write_json
from ...prompts.marks import EMPTY_IMAGE_MARK
from .cache import sampling_record
from .render import encode_page
from .transcribe import _ask_twice, _cause, _unfinished, _unwrap_markdown_fence


# Left where a picture stood when nothing could be read off it — a metafile Pillow cannot
# open, or a call that failed after its retries. Visible on purpose, like the failed page:
# a formula that silently vanished from an exercise is worse than one that says it is gone.

# Where the transcription of each picture is cached, keyed by the picture's content and
# shared by every document of the workspace: one file per distinct image, so the header
# logo six documents repeat costs one call and not six.
IMAGES_DIR_NAME = "images"


def _encode_image(image) -> bytes:
    """Return the picture as PNG bytes, on white and no smaller than the model can read.

    Transparency is composited onto white: a formula drawn in black on a transparent ground
    is invisible on the black a preprocessor pads with. A small picture is upscaled by a
    whole factor until its longer side reaches `TRANSCRIBE_IMAGE_MIN_LONG_SIDE` — compositing
    onto white is needed either way, a formula drawn in black on a transparent ground
    vanishing on a black pad.
    """
    from PIL import Image

    if image.mode in ("RGBA", "LA", "P"):
        rgba = image.convert("RGBA")
        flat = Image.new("RGB", rgba.size, "white")
        flat.paste(rgba, mask=rgba.getchannel("A"))
        image = flat
    elif image.mode != "RGB":
        image = image.convert("RGB")
    longest = max(image.size)
    min_side = config.TRANSCRIBE_IMAGE_MIN_LONG_SIDE
    max_pixels = config.TRANSCRIBE_IMAGE_MAX_PIXELS
    if 0 < longest < min_side:
        factor = -(-min_side // longest)
        image = image.resize(
            (image.width * factor, image.height * factor), Image.Resampling.LANCZOS
        )
    elif image.width * image.height > max_pixels:
        # A photograph pasted whole into a document is the page scan's twin: shrunk to what
        # a render of two A4 pages at 200 dpi holds, which is more than the endpoint reads.
        factor = (max_pixels / (image.width * image.height)) ** 0.5
        image = image.resize(
            (max(1, round(image.width * factor)), max(1, round(image.height * factor))),
            Image.Resampling.LANCZOS,
        )
    # The same bytes as always for every picture that fits, so its cached reading — keyed by
    # them — stays a hit; only a picture heavy enough to threaten the request changes route.
    return encode_page(image, scanned=False)


# What of an image record says how the picture was sampled.
_SAMPLING_FIELDS = ("temperature", "top_k", "top_p")


def _read_image_cache(images_dir: str | Path | None, digest: str, model: str) -> str | None:
    """The cached reading of a picture, when it was made under the same model and sampling."""
    if images_dir is None:
        return None
    path = _image_record_path(Path(images_dir), digest)
    if not path.exists():
        return None
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(record, dict) or not isinstance(record.get("text"), str):
        return None
    sampled = {key: record[key] for key in _SAMPLING_FIELDS if key in record}
    if record.get("model") != model or sampled != sampling_record("transcribe_image"):
        return None
    return record["text"]


def _transcribe_image(
    image: str, index: int, count: int, model: str, tag: str, prompts
) -> str | None:
    """Read one picture; `""` for one with nothing on it, `None` when it could not be read.

    Same two attempts as a page (`_ask_twice`). A picture whose answer never finished
    twice is unreadable and NOT salvaged: what comes before the loop in a diagram is half
    a diagram, and half a ```mermaid block is worse than the mark that says the picture
    is missing. It is not cached either, so a later read gets another chance.
    """
    what = f"picture {index}/{count}"
    try:
        answer = _ask_twice(
            model,
            lambda note: prompts.transcribe_image_prompt(index, count, note=note),
            image,
            "transcribe_image",
            config.THINK_TRANSCRIBE_IMAGE,
            tag,
            what,
            prompts,
        )
    except inference.InferenceError as e:
        logger.error(f"{tag}{what}: giving up after the retries ({e})")
        return None
    if _unfinished(answer):
        logger.error(
            f"{tag}{what}: {_cause(answer, config.TRANSCRIBE_MAX_OUTPUT_TOKENS)} on the "
            "second attempt too; marked unreadable"
        )
        return None
    reading = _unwrap_markdown_fence(answer.response)
    stripped = reading.strip()
    if not stripped or (
        EMPTY_IMAGE_MARK in stripped and len(stripped) <= len(EMPTY_IMAGE_MARK) + 16
    ):
        return ""
    return stripped


def _write_image_cache(
    images_dir: str | Path | None, digest: str, model: str, text: str
) -> None:
    """Record one picture's reading beside what it was read with."""
    if images_dir is None:
        return
    write_json(
        _image_record_path(Path(images_dir), digest),
        {
            "sha256": digest,
            "model": model,
            **sampling_record("transcribe_image"),
            "text": text,
        },
    )


def _image_record_path(images_dir: Path, digest: str) -> Path:
    """The file holding one picture's reading, named by the picture's content."""
    return images_dir / f"{digest}.json"
