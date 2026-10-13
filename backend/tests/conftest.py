import hashlib
import math
import re

import pytest

from app.core.config import settings
from app.services import embedding

DIM = 256


def fake_embed(texts):
    out = []
    for text in texts:
        vec = [0.0] * DIM
        for token in re.findall(r"[a-z0-9]+", text.lower()):
            idx = int(hashlib.md5(token.encode()).hexdigest(), 16) % DIM
            vec[idx] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        out.append([v / norm for v in vec])
    return out


@pytest.fixture(autouse=True)
def _local_env(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)
    monkeypatch.setattr(embedding, "embed", fake_embed)
