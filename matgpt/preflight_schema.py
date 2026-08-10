"""Stable, dependency-light schema shared by preflight producers and consumers."""

CHECK_IDS = (
    "config",
    "source_revision",
    "dataset_manifest",
    "dataset_overlap",
    "tokenizer",
    "shards",
    "output_storage",
    "device",
    "training_math",
    "checkpoint",
)
