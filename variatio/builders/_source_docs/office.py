"""Rasterising the metafiles of an Office document before Docling reads it.

Word and PowerPoint embed the Equation Editor's equations, clip art and most logos as EMF
or WMF metafiles, and Pillow opens neither — so Docling hands them over as pictures with no
image, and the equations of a whole workbook read as `[IMAGEN NO LEGIBLE]`. Docling's own
LibreOffice fallback does not reach them: it covers VML and DrawingML shapes, never an
`a:blip` pointing at a metafile. So the rasterising is done here, on a COPY of the file:
every metafile under `media/` becomes a PNG rendered by LibreOffice, the relationships and
the content types are rewritten to point at it, and Docling opens the copy with Pillow like
any other picture. The original is never touched and the cache keys on it alone.
"""

import re
import shutil
import subprocess
import zipfile
from pathlib import Path

from loguru import logger

METAFILE_EXTS = (".emf", ".wmf")

# LibreOffice draws an imported metafile at its natural size in the middle of a page and
# exports the PAGE; asked for both pixel dimensions it renders that page at any resolution.
# 4× the 96-dpi page is 384 dpi, which turns a 96×13 px equation into 380×54: vector
# resolution rather than an upscale. The PDF route was measured and rejected — it dropped
# the text half of the reference workbook's crown logo, where the PNG export kept it.
RASTER_SCALE = 4
# Around the drawing when the page is cropped to it; at 4× this is four points of paper.
CONTENT_MARGIN_PX = 16
# A metafile with nothing on it still has to become a picture the model can answer
# `EMPTY_IMAGE_MARK` to — once, since every such picture hashes the same.
BLANK_SIDE_PX = 64
CONVERT_TIMEOUT_SECONDS = 180

_RELS_TARGET_RE = r'(Target="[^"]*?){name}"'
_PNG_DEFAULT = '<Default Extension="png" ContentType="image/png"/>'


def rasteriser() -> str | None:
    """Return the LibreOffice binary on the PATH, or `None` when there is none.

    Looked up at call time and never cached: installing LibreOffice must not need a
    restart, and the fingerprint asks the same question to expire what was read without it.
    """
    return shutil.which("soffice") or shutil.which("libreoffice")


def metafiles(source: str | Path) -> list[str]:
    """The zip entries of an Office file that are EMF or WMF pictures, in archive order."""
    try:
        with zipfile.ZipFile(source) as archive:
            return [
                name
                for name in archive.namelist()
                if "/media/" in name and name.lower().endswith(METAFILE_EXTS)
            ]
    except (zipfile.BadZipFile, OSError):
        return []


def rasterised_copy(source: str | Path, workdir: str | Path) -> Path | None:
    """Write a copy of `source` whose metafiles are PNGs, or `None` when there is nothing to do.

    `None` means «read the original»: the file carries no metafile, it is not a zip at all
    (Docling will say so in its own words), or there is no LibreOffice to render with — in
    which case the pictures stay unreadable and the document says so, picture by picture.
    A metafile LibreOffice could not render is left as it was, for the same reason.
    """
    source = Path(source)
    names = metafiles(source)
    if not names:
        return None
    tool = rasteriser()
    if tool is None:
        logger.warning(
            f"[{source.name}] {len(names)} EMF/WMF picture(s) cannot be read: LibreOffice "
            "(soffice) is not on the PATH"
        )
        return None

    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    rendered = _render(tool, source, names, workdir)
    if not rendered:
        return None
    copy = workdir / source.name
    _rewrite(source, copy, rendered)
    logger.info(f"[{source.name}] {len(rendered)}/{len(names)} metafile(s) rasterised")
    return copy


def _render(tool: str, source: Path, names: list[str], workdir: Path) -> dict[str, bytes]:
    """Render each metafile through LibreOffice, keyed by its zip entry; misses are absent."""
    inputs = workdir / "metafiles"
    inputs.mkdir(parents=True, exist_ok=True)
    by_file: dict[Path, str] = {}
    with zipfile.ZipFile(source) as archive:
        for index, name in enumerate(names):
            # Numbered rather than named after the entry: two parts may hold a file of the
            # same basename, and LibreOffice names its output after the input's stem.
            path = inputs / f"{index:03d}{Path(name).suffix.lower()}"
            path.write_bytes(archive.read(name))
            by_file[path] = name

    outputs = workdir / "png"
    # Two passes, because the export needs the page's pixel size to keep its aspect and
    # LibreOffice picks the page (Letter here, A4 under another locale) on its own: the
    # first pass at the default 96 dpi says how big the page is, the second renders it at
    # `RASTER_SCALE` times that.
    page = _export(tool, list(by_file), outputs / "probe", workdir, None)
    if not page:
        return {}
    probe = _open_png(next(iter(page.values())))
    if probe is None:
        return {}
    size = (probe.width * RASTER_SCALE, probe.height * RASTER_SCALE)
    full = _export(tool, list(by_file), outputs / "full", workdir, size)

    out: dict[str, bytes] = {}
    for path, name in by_file.items():
        rendered = full.get(path.stem) or page.get(path.stem)
        image = _open_png(rendered) if rendered else None
        if image is None:
            logger.warning(f"[{source.name}] '{name}' could not be rasterised; left as it is")
            continue
        out[name] = crop_to_content(image)
    return out


def _export(
    tool: str, inputs: list[Path], outdir: Path, workdir: Path, size: tuple[int, int] | None
) -> dict[str, Path]:
    """Run one LibreOffice export over `inputs`, returning the PNGs it wrote by stem."""
    outdir.mkdir(parents=True, exist_ok=True)
    target = "png"
    if size is not None:
        target += (
            ':draw_png_Export:{"PixelWidth":{"type":"long","value":"%d"},'
            '"PixelHeight":{"type":"long","value":"%d"}}' % size
        )
    # A profile of its own per run: LibreOffice refuses to start while another instance
    # holds the default profile's lock, and two documents may be read at once.
    profile = (workdir / "profile").resolve()
    command = [
        tool,
        "--headless",
        "--norestore",
        f"-env:UserInstallation={profile.as_uri()}",
        "--convert-to",
        target,
        "--outdir",
        str(outdir),
        *(str(path) for path in inputs),
    ]
    try:
        subprocess.run(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=CONVERT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        logger.warning(f"LibreOffice export failed ({e})")
        return {}
    return {path.stem: path for path in outdir.glob("*.png")}


def _open_png(path: Path):
    """Open a rendered page, `None` when LibreOffice wrote nothing readable."""
    from PIL import Image, UnidentifiedImageError

    try:
        image = Image.open(path)
        image.load()
        return image
    except (UnidentifiedImageError, OSError):
        return None


def crop_to_content(image) -> bytes:
    """Return the page as PNG bytes cropped to what is drawn on it, plus a margin.

    The page is white and so is the paper a drawing is normally on, so the content is
    whatever is not white; a page with nothing on it becomes a small blank picture rather
    than nothing, so the model can say so once and the answer is cached.
    """
    import io

    from PIL import Image, ImageChops

    flat = _on_white(image)
    box = ImageChops.difference(flat, Image.new("RGB", flat.size, "white")).getbbox()
    if box is None:
        flat = Image.new("RGB", (BLANK_SIDE_PX, BLANK_SIDE_PX), "white")
    else:
        flat = flat.crop(
            (
                max(0, box[0] - CONTENT_MARGIN_PX),
                max(0, box[1] - CONTENT_MARGIN_PX),
                min(flat.width, box[2] + CONTENT_MARGIN_PX),
                min(flat.height, box[3] + CONTENT_MARGIN_PX),
            )
        )
    buffer = io.BytesIO()
    flat.save(buffer, format="PNG")
    return buffer.getvalue()


def _on_white(image):
    """The image as RGB over white, whatever it was."""
    from PIL import Image

    if image.mode in ("RGBA", "LA", "P"):
        rgba = image.convert("RGBA")
        flat = Image.new("RGB", rgba.size, "white")
        flat.paste(rgba, mask=rgba.getchannel("A"))
        return flat
    return image.convert("RGB")


def _rewrite(source: Path, copy: Path, rendered: dict[str, bytes]) -> None:
    """Write the copy: each rendered metafile as `<entry>.png`, references and types updated.

    The PNG keeps the metafile's whole name plus `.png` — `image1.emf.png` — so it can never
    collide with a picture the archive already holds, and the relationship rewrite matches
    the basename right before its closing quote, so `image1.emf` never touches `image10.emf`.
    """
    renamed = {name: f"{name}.png" for name in rendered}
    basenames = {Path(name).name: Path(new).name for name, new in renamed.items()}
    with zipfile.ZipFile(source) as archive, zipfile.ZipFile(
        copy, "w", compression=zipfile.ZIP_DEFLATED
    ) as out:
        for info in archive.infolist():
            name = info.filename
            if name in renamed:
                out.writestr(renamed[name], rendered[name])
                continue
            data = archive.read(name)
            if name.endswith(".rels"):
                data = _rewrite_targets(data, basenames)
            elif name == "[Content_Types].xml":
                data = _declare_png(data)
            out.writestr(info, data)


def _rewrite_targets(data: bytes, basenames: dict[str, str]) -> bytes:
    """Point every relationship at the PNG that replaced its metafile."""
    text = data.decode("utf-8")
    for old, new in basenames.items():
        text = re.sub(_RELS_TARGET_RE.format(name=re.escape(old)), rf'\g<1>{new}"', text)
    return text.encode("utf-8")


def _declare_png(data: bytes) -> bytes:
    """Make sure the package declares the `png` extension, which a metafile-only one may not."""
    text = data.decode("utf-8")
    if re.search(r'<Default\s+Extension="png"', text, re.IGNORECASE):
        return data
    return text.replace("</Types>", f"{_PNG_DEFAULT}</Types>").encode("utf-8")
