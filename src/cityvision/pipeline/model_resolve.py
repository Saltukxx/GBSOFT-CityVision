from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

from cityvision.config import ROOT

PathLike = Union[str, Path]


@dataclass(frozen=True)
class ModelBSpec:
    """Resolved Model B weights plus optional per-weight class filter."""

    path: Path
    allowed_classes: Optional[tuple[str, ...]] = None

    @property
    def name(self) -> str:
        return self.path.name

    def __str__(self) -> str:
        return str(self.path)

    def __fspath__(self) -> str:
        return str(self.path)


def _as_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value if v]
    return [str(value)]


def _parse_model_b_item(item: Any) -> Optional[tuple[str, Optional[tuple[str, ...]]]]:
    """Return (path, allowed_classes) from a list string or {path, allowed_classes} map."""
    if item is None or item is False:
        return None
    if isinstance(item, dict):
        path = item.get("path")
        if not path:
            return None
        allowed = item.get("allowed_classes")
        if allowed is None:
            return str(path), None
        if isinstance(allowed, str):
            classes = (allowed,) if allowed else ()
        else:
            classes = tuple(str(c) for c in allowed if c)
        return str(path), classes or None
    text = str(item).strip()
    if not text:
        return None
    return text, None


def _resolve_existing(path: PathLike) -> Optional[Path]:
    p = Path(path)
    if not p.is_absolute():
        cand = (ROOT / p).resolve()
        if cand.exists():
            return cand
        cwd = Path.cwd() / p
        if cwd.exists():
            return cwd.resolve()
        return None
    return p if p.exists() else None


def resolve_model_b_paths(
    det_cfg: Dict[str, Any],
    cli_model_b: Optional[PathLike] = None,
) -> List[ModelBSpec]:
    """
    Resolve infrastructure Model B weights.

    Priority:
      1) CLI --model-b (single override, still merges with list if auto)
      2) detection.model_b_list (string path or {path, allowed_classes})
      3) detection.model_b (legacy string)
      4) auto-discover models/infra-b-*.pt
      5) optional fallbacks (e.g. in-progress training best.pt)

    Missing files are skipped so waste can appear automatically when training exports.
    """
    found: List[ModelBSpec] = []
    seen: set[str] = set()

    def add(path: PathLike, allowed_classes: Optional[tuple[str, ...]] = None) -> None:
        resolved = _resolve_existing(path)
        if resolved is None:
            return
        key = str(resolved)
        if key in seen:
            return
        seen.add(key)
        found.append(ModelBSpec(path=resolved, allowed_classes=allowed_classes))

    if cli_model_b:
        add(cli_model_b)

    raw_list = det_cfg.get("model_b_list")
    if raw_list is None:
        items: List[Any] = []
    elif isinstance(raw_list, (list, tuple)):
        items = list(raw_list)
    else:
        items = [raw_list]
    for item in items:
        parsed = _parse_model_b_item(item)
        if parsed is None:
            continue
        add(parsed[0], parsed[1])

    # legacy single field (may already be in list)
    if det_cfg.get("model_b"):
        add(det_cfg.get("model_b"))

    if bool(det_cfg.get("auto_discover_model_b", True)):
        models_dir = ROOT / "models"
        if models_dir.exists():
            for pt in sorted(models_dir.glob("infra-b-*.pt")):
                add(pt)

    loaded_names = " ".join(p.name.lower() for p in found)
    for item in _as_list(det_cfg.get("model_b_fallbacks")):
        # Prefer exported models/infra-b-waste.pt over in-progress training best.pt
        item_l = str(item).lower()
        if "waste" in item_l and "waste" in loaded_names:
            continue
        if "road" in item_l and "road" in loaded_names:
            continue
        add(item)

    return found


def describe_models(paths: Sequence[Union[Path, ModelBSpec]]) -> str:
    if not paths:
        return "none"
    return "+".join(
        p.name if isinstance(p, ModelBSpec) else Path(p).name for p in paths
    )
