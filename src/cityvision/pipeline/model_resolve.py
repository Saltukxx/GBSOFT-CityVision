from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Union

from cityvision.config import ROOT

PathLike = Union[str, Path]


def _as_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value if v]
    return [str(value)]


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
) -> List[Path]:
    """
    Resolve infrastructure Model B weights.

    Priority:
      1) CLI --model-b (single override, still merges with list if auto)
      2) detection.model_b_list
      3) detection.model_b (legacy string)
      4) auto-discover models/infra-b-*.pt
      5) optional fallbacks (e.g. in-progress training best.pt)

    Missing files are skipped so waste can appear automatically when training exports.
    """
    found: List[Path] = []
    seen: set[str] = set()

    def add(path: PathLike) -> None:
        resolved = _resolve_existing(path)
        if resolved is None:
            return
        key = str(resolved)
        if key in seen:
            return
        seen.add(key)
        found.append(resolved)

    if cli_model_b:
        add(cli_model_b)

    for item in _as_list(det_cfg.get("model_b_list")):
        add(item)

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


def describe_models(paths: Sequence[Path]) -> str:
    if not paths:
        return "none"
    return "+".join(p.name for p in paths)
