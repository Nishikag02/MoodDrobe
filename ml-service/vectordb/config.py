"""Shared paths and settings. Every value can be overridden with an
environment variable so nothing machine-specific is hard-coded."""

import os
from pathlib import Path

# ml-service/ folder (this file lives in ml-service/vectordb/)
ML_ROOT = Path(__file__).resolve().parent.parent

PRODUCTS_CSV = Path(
    os.getenv("MOODDROBE_PRODUCTS_CSV", ML_ROOT / "data/catalogue/metadata/products.csv")
)
EMBEDDINGS_DIR = Path(
    os.getenv(
        "MOODDROBE_EMBEDDINGS_DIR",
        ML_ROOT / "data/processed/catalogue_embeddings/full_catalogue_v2",
    )
)
RAW_DATA_DIR = Path(os.getenv("MOODDROBE_RAW_DIR", ML_ROOT / "data/raw/deepfashion"))
REPORTS_DIR = Path(os.getenv("MOODDROBE_REPORTS_DIR", ML_ROOT / "data/processed/reports"))
# Dominant-colour palettes of the catalogue (scripts/extract_colors.py)
COLORS_DIR = Path(os.getenv("MOODDROBE_COLORS_DIR", ML_ROOT / "data/processed/colors"))

EMBEDDING_DIM = 512
CHUNK_SIZE = int(os.getenv("MOODDROBE_CHUNK_SIZE", "5000"))
SPLITS = ("train", "val", "test")

# Qdrant: a server URL (Docker) by default. Set QDRANT_PATH instead to use
# Qdrant's embedded local mode (no Docker, slower, fine for small tests).
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_PATH = os.getenv("QDRANT_PATH")  # e.g. data/processed/qdrant_local
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "mooddrobe_catalogue_v2")
