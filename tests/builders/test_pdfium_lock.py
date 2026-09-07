"""PDFium is not thread-safe, so every call into it goes through one process-wide lock.

Measured: the request thread counting pages for `/raw` while the job thread rendered them
corrupts PDFium's global state, and from that moment every PDF of the process fails to load
("Data format error") until a restart.
"""

import sys
import threading
from types import SimpleNamespace

import pytest

from variatio.builders.source_docs import pages


class _Lock:
    """An RLock that records whether it is held by the calling thread."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.depth = 0

    def __enter__(self):
        self._lock.acquire()
        self.depth += 1

    def __exit__(self, *exc):
        self.depth -= 1
        self._lock.release()

    @property
    def held(self) -> bool:
        return self.depth > 0


class _Fake:
    """A stand-in for `pypdfium2` that refuses any call made outside the lock."""

    def __init__(self, lock: _Lock, count: int = 3) -> None:
        self.lock = lock
        self.count = count
        self.calls: list[str] = []
        self.closed = 0

    def _touch(self, what: str) -> None:
        assert self.lock.held, f"{what} was called without the PDFium lock"
        self.calls.append(what)

    def PdfDocument(self, path: str):
        self._touch("open")
        fake = self

        class Page:
            def render(self, scale):
                fake._touch("render")
                return SimpleNamespace(to_pil=lambda: _Image(fake))

            def close(self):
                fake._touch("page.close")

        class Document:
            def __len__(self):
                fake._touch("len")
                return fake.count

            def __getitem__(self, index):
                fake._touch("page")
                return Page()

            def close(self):
                fake._touch("close")
                fake.closed += 1

        return Document()


class _Image:
    def __init__(self, fake: _Fake) -> None:
        self.fake = fake

    def save(self, buffer, format):
        self.fake._touch("png")
        buffer.write(b"png")


@pytest.fixture
def fake(monkeypatch) -> _Fake:
    lock = _Lock()
    fake = _Fake(lock)
    monkeypatch.setattr(pages, "_PDFIUM_LOCK", lock)
    monkeypatch.setitem(sys.modules, "pypdfium2", fake)
    return fake


def test_counting_pages_holds_the_lock_and_closes_the_document(fake: _Fake) -> None:
    assert pages.page_count("any.pdf") == 3
    assert fake.calls == ["open", "len", "close"]
    assert not fake.lock.held


def test_every_render_holds_the_lock_and_releases_it_between_pages(fake: _Fake) -> None:
    count, images = pages.page_images("any.pdf", dpi=72)
    assert count == 3
    assert not fake.lock.held, "the lock must not be held while the model reads a page"
    seen = []
    for image in images:
        assert not fake.lock.held
        seen.append(image)
    assert len(seen) == 3
    assert fake.calls.count("render") == 3
    assert fake.calls.count("page.close") == 3
    assert fake.closed == 1


def test_an_abandoned_render_still_closes_the_document(fake: _Fake) -> None:
    _, images = pages.page_images("any.pdf", dpi=72)
    next(images)
    images.close()
    assert fake.closed == 1
    assert not fake.lock.held


def test_resuming_past_the_end_renders_nothing_and_closes(fake: _Fake) -> None:
    count, images = pages.page_images("any.pdf", dpi=72, first=9)
    assert count == 3
    assert list(images) == []
    assert fake.closed == 1
