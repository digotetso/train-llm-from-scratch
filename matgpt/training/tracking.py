from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass
class NullTracker:
    """No-op tracker used when experiment logging is disabled.

    The training loop always calls `tracker.log(...)`. When W&B is disabled,
    this object absorbs those calls so the training code stays simple.
    """

    def log(self, metrics: Mapping[str, Any], step: int | None = None) -> None:
        return None

    def finish(self) -> None:
        return None


class WandbTracker:
    """Small W&B wrapper that keeps the rest of the code independent of wandb."""

    def __init__(self, run: Any) -> None:
        self.run = run

    def log(self, metrics: Mapping[str, Any], step: int | None = None) -> None:
        self.run.log(dict(metrics), step=step)

    def finish(self) -> None:
        self.run.finish()


def normalize_wandb_entity(value: Any) -> str | None:
    if value is None:
        return None
    entity = str(value).strip().strip("/")
    if not entity:
        return None
    if "/" in entity:
        raise ValueError(
            "tracking.wandb.entity must be only a W&B username or team name, not a path."
        )
    return entity


def create_tracker(cfg: dict[str, Any], config_snapshot: dict[str, Any]) -> NullTracker | WandbTracker:
    wandb_cfg = cfg.get("tracking", {}).get("wandb", {})
    if not wandb_cfg.get("enabled", False):
        return NullTracker()

    try:
        import wandb
    except ImportError as exc:
        raise RuntimeError("Install wandb or set tracking.wandb.enabled=false.") from exc

    run = wandb.init(
        project=wandb_cfg["project"],
        entity=normalize_wandb_entity(wandb_cfg.get("entity")),
        name=cfg["run"]["name"],
        tags=wandb_cfg.get("tags") or [],
        config=config_snapshot,
        save_code=True,
    )
    return WandbTracker(run)
