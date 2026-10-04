from dataclasses import replace
from pathlib import Path
import numpy as np
import pytest
from rfp_intelligence.config import Config
from rfp_intelligence.search.service import SearchService, tokenize


class Tokenizer:
    model_max_length = 512
    def encode(self, text, add_special_tokens=True):
        return text.split()
    def decode(self, tokens):
        return " ".join(tokens)


class Embedder:
    tokenizer = Tokenizer()
    def encode(self, texts, **kwargs):
        return np.array([[text.lower().count(word) + .1 for word in ["warranty", "deadline", "sku", "laptop"]] for text in texts])


class Reranker:
    def predict(self, pairs):
        return [len(set(tokenize(q)) & set(tokenize(text))) for q, text in pairs]


@pytest.fixture
def config(tmp_path):
    return replace(Config.load(), data_dir=tmp_path / "data", output_dir=tmp_path / "out", data_root=tmp_path)


@pytest.fixture
def service(config):
    result = SearchService(config, Embedder(), Reranker())
    yield result
    result.close()


def write_bid(root, name="Example", text="Laptop SKU ABC-123. Warranty three years. Deadline July 9."):
    folder = root / name
    folder.mkdir(exist_ok=True)
    (folder / "portal.html").write_text(f"<main><h1>Computing equipment</h1><p>{text}</p></main>", encoding="utf-8")
    return folder
