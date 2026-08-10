import json
from pathlib import Path

import numpy as np


DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "embedded_documents.json"

with open(DATA_FILE, "r", encoding="utf-8") as f:
    documents = json.load(f)

embeddings = np.array(
    [doc["embedding"] for doc in documents],
    dtype=np.float32,
)
