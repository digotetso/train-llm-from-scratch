"""Validated source registry for the Telco 300M data pipeline.

The registry is the trust boundary between assets that may be used for base
pretraining and assets reserved for post-training, retrieval, or evaluation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml


PRETRAIN_ROLES = frozenset(
    {"pretrain_general", "pretrain_telecom", "pretrain_structured"}
)
ASSET_ROLES = PRETRAIN_ROLES | frozenset(
    {"posttrain", "rag_only", "evaluation_only"}
)
LICENSE_REVIEW_STATES = frozenset({"required", "cleared"})
IMMUTABLE_REVISION = re.compile(r"^[0-9a-fA-F]{40}$")

SOURCE_KEYS = frozenset(
    {
        "id",
        "hf_name",
        "hf_config",
        "split",
        "revision",
        "role",
        "license",
        "license_review",
        "text_field",
        "document_id_field",
        "collection",
        "collection_field",
        "license_field",
        "token_count_field",
        "data_files",
        "buckets",
    }
)
BUCKET_KEYS = frozenset({"id", "collections", "weight"})


def _nonempty_string(value: Any, field: str, owner: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Source {owner!r} requires non-empty {field!r}.")
    return value.strip()


def _optional_string(value: Any, field: str, owner: str) -> str | None:
    if value is None:
        return None
    return _nonempty_string(value, field, owner)


def _string_tuple(value: Any, field: str, owner: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError(f"Source {owner!r} field {field!r} must be a list.")
    items = tuple(_nonempty_string(item, field, owner) for item in value)
    if len(items) != len(set(items)):
        raise ValueError(f"Source {owner!r} field {field!r} contains duplicates.")
    return items


@dataclass(frozen=True)
class SourceBucket:
    """A quota bucket selected from a categorical field in one source."""

    id: str
    collections: tuple[str, ...]
    weight: float


@dataclass(frozen=True)
class SourceSpec:
    """One immutable upstream dataset definition."""

    id: str
    hf_name: str
    hf_config: str | None
    split: str
    revision: str
    role: str
    license: str
    license_review: str
    text_field: str | None
    document_id_field: str | None
    collection: str | None
    collection_field: str | None
    license_field: str | None
    token_count_field: str | None
    data_files: tuple[str, ...]
    buckets: tuple[SourceBucket, ...]

    @property
    def bucket_by_id(self) -> dict[str, SourceBucket]:
        return {bucket.id: bucket for bucket in self.buckets}


@dataclass(frozen=True)
class SourceRegistry:
    """A validated, versioned set of data assets."""

    version: int
    sources: tuple[SourceSpec, ...]

    @property
    def by_id(self) -> dict[str, SourceSpec]:
        return {source.id: source for source in self.sources}


def _parse_bucket(raw: Any, source_id: str) -> SourceBucket:
    if not isinstance(raw, Mapping):
        raise ValueError(f"Source {source_id!r} buckets must be mappings.")
    unknown = set(raw) - BUCKET_KEYS
    if unknown:
        raise ValueError(
            f"Source {source_id!r} bucket contains unknown keys: {sorted(unknown)}"
        )
    bucket_id = _nonempty_string(raw.get("id"), "bucket.id", source_id)
    collections = _string_tuple(
        raw.get("collections"), "bucket.collections", source_id
    )
    if not collections:
        raise ValueError(
            f"Source {source_id!r} bucket {bucket_id!r} requires collections."
        )
    weight = raw.get("weight")
    if not isinstance(weight, (int, float)) or isinstance(weight, bool):
        raise ValueError(
            f"Source {source_id!r} bucket {bucket_id!r} requires numeric weight."
        )
    weight = float(weight)
    if weight < 0:
        raise ValueError(
            f"Source {source_id!r} bucket {bucket_id!r} has negative weight."
        )
    return SourceBucket(id=bucket_id, collections=collections, weight=weight)


def _parse_source(raw: Any, *, serious: bool) -> SourceSpec:
    if not isinstance(raw, Mapping):
        raise ValueError("Every source entry must be a mapping.")
    source_id = _nonempty_string(raw.get("id"), "id", "<unknown>")
    unknown = set(raw) - SOURCE_KEYS
    if unknown:
        raise ValueError(
            f"Source {source_id!r} contains unknown keys: {sorted(unknown)}"
        )

    revision = _nonempty_string(raw.get("revision"), "revision", source_id)
    if serious and IMMUTABLE_REVISION.fullmatch(revision) is None:
        raise ValueError(
            f"Source {source_id!r} requires an immutable 40-character revision."
        )

    role = _nonempty_string(raw.get("role"), "role", source_id)
    if role not in ASSET_ROLES:
        raise ValueError(
            f"Source {source_id!r} has unknown role {role!r}; "
            f"expected one of {sorted(ASSET_ROLES)}."
        )

    review = _nonempty_string(
        raw.get("license_review"), "license_review", source_id
    )
    if review not in LICENSE_REVIEW_STATES:
        raise ValueError(
            f"Source {source_id!r} has unknown license_review {review!r}."
        )

    text_field = _optional_string(raw.get("text_field"), "text_field", source_id)
    if role in PRETRAIN_ROLES and text_field is None:
        raise ValueError(
            f"Pretraining source {source_id!r} requires non-empty 'text_field'."
        )

    raw_buckets = raw.get("buckets") or []
    if not isinstance(raw_buckets, list):
        raise ValueError(f"Source {source_id!r} field 'buckets' must be a list.")
    buckets = tuple(_parse_bucket(bucket, source_id) for bucket in raw_buckets)
    bucket_ids = [bucket.id for bucket in buckets]
    if len(bucket_ids) != len(set(bucket_ids)):
        raise ValueError(f"Source {source_id!r} has duplicate bucket ids.")
    collection_field = _optional_string(
        raw.get("collection_field"), "collection_field", source_id
    )
    if buckets and collection_field is None:
        raise ValueError(
            f"Source {source_id!r} with buckets requires 'collection_field'."
        )
    collection_values = [
        collection for bucket in buckets for collection in bucket.collections
    ]
    if len(collection_values) != len(set(collection_values)):
        raise ValueError(
            f"Source {source_id!r} assigns a collection to multiple buckets."
        )
    if buckets and abs(sum(bucket.weight for bucket in buckets) - 1.0) > 1.0e-9:
        raise ValueError(f"Source {source_id!r} bucket weights must sum to 1.0.")

    return SourceSpec(
        id=source_id,
        hf_name=_nonempty_string(raw.get("hf_name"), "hf_name", source_id),
        hf_config=_optional_string(raw.get("hf_config"), "hf_config", source_id),
        split=_nonempty_string(raw.get("split"), "split", source_id),
        revision=revision,
        role=role,
        license=_nonempty_string(raw.get("license"), "license", source_id),
        license_review=review,
        text_field=text_field,
        document_id_field=_optional_string(
            raw.get("document_id_field"), "document_id_field", source_id
        ),
        collection=_optional_string(raw.get("collection"), "collection", source_id),
        collection_field=collection_field,
        license_field=_optional_string(
            raw.get("license_field"), "license_field", source_id
        ),
        token_count_field=_optional_string(
            raw.get("token_count_field"), "token_count_field", source_id
        ),
        data_files=_string_tuple(raw.get("data_files"), "data_files", source_id),
        buckets=buckets,
    )


def load_source_registry(
    path: str | Path,
    *,
    serious: bool = True,
) -> SourceRegistry:
    """Load and validate a source registry.

    ``serious=False`` exists only for local experiments with unpinned fixtures.
    Checked training and evaluation workflows always use the default.
    """

    registry_path = Path(path)
    with registry_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    if not isinstance(raw, Mapping):
        raise ValueError(f"Source registry must be a mapping: {registry_path}")
    unknown = set(raw) - {"version", "sources"}
    if unknown:
        raise ValueError(f"Source registry contains unknown keys: {sorted(unknown)}")
    if raw.get("version") != 1:
        raise ValueError("Source registry version must be 1.")
    raw_sources = raw.get("sources")
    if not isinstance(raw_sources, list) or not raw_sources:
        raise ValueError("Source registry requires a non-empty 'sources' list.")

    sources = tuple(_parse_source(source, serious=serious) for source in raw_sources)
    source_ids = [source.id for source in sources]
    if len(source_ids) != len(set(source_ids)):
        duplicates = sorted(
            {source_id for source_id in source_ids if source_ids.count(source_id) > 1}
        )
        raise ValueError(f"Duplicate source id(s): {duplicates}")
    return SourceRegistry(version=1, sources=sources)


def select_pretraining_sources(
    registry: SourceRegistry,
    source_ids: Iterable[str],
) -> tuple[SourceSpec, ...]:
    """Resolve sources and reject any asset not approved for base pretraining."""

    resolved: list[SourceSpec] = []
    by_id = registry.by_id
    for source_id in source_ids:
        if source_id not in by_id:
            raise ValueError(f"Unknown source id: {source_id!r}")
        source = by_id[source_id]
        if source.role not in PRETRAIN_ROLES:
            raise ValueError(
                f"Source {source_id!r} with role {source.role!r} is not permitted "
                "for pretraining."
            )
        resolved.append(source)
    return tuple(resolved)
