"""A subject's tree on disk: provisioning, measuring, emptying the cache, deleting.

Every deletion goes through `_contained_root`, which refuses any path that is not a direct
child of `WORKSPACES_DIR`: the slug arrives in a request, and `shutil.rmtree` on a
mis-resolved path cannot be undone.
"""

import shutil
from pathlib import Path

from variatio.core import paths
from variatio.core.workspace import Workspace


def provision(ws: Workspace) -> None:
    """Create a workspace's directory tree.

    A workspace is a tree before it is a row: the row without the tree leaves every screen
    reporting a missing artifact for a reason nobody could act on.
    """
    for directory in (
        ws.artifacts_dir,
        ws.cache_dir,
        ws.raw_corpus_dir,
        ws.raw_exemplars_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)


def destroy(ws: Workspace) -> bool:
    """Delete a workspace's whole tree, and report whether there was one."""
    root = _contained_root(ws)
    if not root.is_dir():
        return False
    shutil.rmtree(root)
    return True


def disk_usage(ws: Workspace) -> dict[str, int]:
    """What each part of the tree weighs, by role.

    `artifacts` excludes the history it contains, which is reported on its own: it is the
    one thing there that grows without a build — with the generated exercises, which grow
    with every run.
    """
    history = _tree_size(ws.history_dir)
    artifacts = _tree_size(ws.artifacts_dir) - history
    usage = {
        "raw": _tree_size(ws.raw_dir),
        "artifacts": max(0, artifacts),
        "cache": _tree_size(ws.cache_dir),
        "history": history,
        "generations": _tree_size(ws.generations_dir),
    }
    usage["total"] = sum(usage.values())
    return usage


def _tree_size(path: Path) -> int:
    """Total the bytes of a file or of everything under a directory."""
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    return sum(entry.stat().st_size for entry in path.rglob("*") if entry.is_file())


def clear_cache(ws: Workspace) -> dict:
    """Empty the regenerable half of `cache/`: the vectors and the converted markdown.

    The concept descriptions and the corpus anchoring stay — they cost a long model run,
    and emptying a stage is what removes them with the artifact they describe.
    """
    root = _contained_root(ws)
    targets = [ws.cache_dir / "embeddings", ws.markdown_cache_dir]
    removed = 0
    freed = 0
    for target in targets:
        if not target.is_dir():
            continue
        if not target.resolve().is_relative_to(root):
            continue
        for entry in target.rglob("*"):
            if entry.is_file():
                freed += entry.stat().st_size
                removed += 1
        shutil.rmtree(target)
    return {"files_removed": removed, "bytes_freed": freed}


def _contained_root(ws: Workspace) -> Path:
    """Return the workspace root, refusing anything that is not a direct child of the tree.

    Not decorative: the slug arrives in a request and `shutil.rmtree` on a mis-resolved
    path cannot be undone. `Workspace.__post_init__` already resolves it, so comparing is
    enough.
    """
    root = ws.root
    parent = Path(paths.WORKSPACES_DIR).resolve()
    if root.parent != parent or root == parent:
        raise ValueError(f"'{root}' no está dentro de '{parent}': no se borra nada.")
    return root
