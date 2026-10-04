import hashlib
import json
import re
import threading
import uuid
from pathlib import Path
import numpy as np
from rank_bm25 import BM25Okapi
from qdrant_client import QdrantClient, models
from rfp_intelligence.config import Config
from rfp_intelligence.ingestion.parsers import parse, classify
from rfp_intelligence.search.chunks import chunks
from rfp_intelligence.schemas import Evidence, SearchRequest
from rfp_intelligence.storage import Store

SYNONYMS = {"deadline": "due date closing submission", "affidavit": "required forms documentation",
            "warranty": "support coverage extended warranty", "bond": "bid security percentage",
            "payment": "invoice net payment terms", "delivery": "delivery schedule shipment"}


def tokenize(text):
    # Include complete hyphenated identifiers and their components.
    full = re.findall(r"[\w]+(?:[-/#.][\w]+)*", text.lower())
    return full + [part for word in full if "-" in word for part in word.split("-")]


def expand(query):
    return query + " " + " ".join(value for key, value in SYNONYMS.items() if key in query.lower())


def rrf(rankings, constant=60):
    scores = {}
    for ranking in rankings:
        for rank, key in enumerate(ranking, 1):
            scores[key] = scores.get(key, 0) + 1 / (constant + rank)
    return sorted(scores, key=lambda k: (-scores[k], k)), scores


class SearchService:
    def __init__(self, config: Config, embedder=None, reranker=None):
        self.config = config
        self.store = Store(config.data_dir)
        self.client = QdrantClient(path=str(config.data_dir / "qdrant"))
        self._embedder, self._reranker = embedder, reranker
        self.lock = threading.RLock()
        # Embedding versions never share a vector collection.
        self.collection = "chunks_" + hashlib.sha256(config.embedding_model.encode()).hexdigest()[:12]

    @property
    def embedder(self):
        if self._embedder is None:
            from sentence_transformers import SentenceTransformer
            self._embedder = SentenceTransformer(self.config.embedding_model, cache_folder=str(self.config.data_dir / "models"))
        return self._embedder

    @property
    def reranker(self):
        if self._reranker is None:
            from sentence_transformers import CrossEncoder
            self._reranker = CrossEncoder(self.config.rerank_model, cache_folder=str(self.config.data_dir / "models"))
        return self._reranker

    def close(self):
        self.client.close()

    def index(self, folder: str | Path):
        folder = self.config.bid_path(folder)
        bid = folder.name
        if not re.fullmatch(r"[\w .-]+", bid):
            raise ValueError("Bid folder name contains unsupported characters")
        base_version = f"parser-v5/chunks-350-50/{self.config.embedding_model}"
        report = {"bid_id": bid, "indexed": [], "skipped": [], "deleted": [], "errors": [], "warnings": []}
        with self.lock:
            manifest = self.store.manifests(bid)
            paths = sorted(p for p in folder.iterdir() if p.suffix.lower() in {".pdf", ".html", ".htm"})
            if not paths:
                raise ValueError("No PDF or HTML files found in bid folder")
            for path in paths:
                # Only the specs continuation stage changed in this revision.
                stage = {"specs": "/specs-continuation-v2", "addendum": "/addendum-page-v2"}.get(classify(path, "")[0], "")
                version = base_version + stage
                fingerprint = hashlib.sha256(path.read_bytes()).hexdigest()
                old = manifest.get(path.name)
                if old and old["fingerprint"] == fingerprint and old["version"] == version:
                    report["skipped"].append(path.name)
                    report["warnings"].extend(json.loads(old["warnings"]))
                    continue
                generation = str(uuid.uuid4())
                try:
                    blocks, warnings = parse(path, bid)
                    evidence = chunks(blocks, self.embedder.tokenizer)
                    if not evidence:
                        raise ValueError("No indexable text; empty or scanned document")
                    vectors = self.embedder.encode([f"{e.doc_type}: {e.heading}\n{e.text}" for e in evidence],
                                                    normalize_embeddings=True, show_progress_bar=False)
                    if not self.client.collection_exists(self.collection):
                        self.client.create_collection(self.collection, vectors_config=models.VectorParams(size=len(vectors[0]), distance=models.Distance.COSINE))
                    points = [models.PointStruct(id=str(uuid.uuid5(uuid.NAMESPACE_URL, e.id + generation)),
                                                  vector=np.asarray(v).tolist(), payload={"generation": generation,
                                                  "id": e.id, "bid_id": bid, "doc_type": e.doc_type,
                                                  "addendum_number": e.addendum_number}) for e, v in zip(evidence, vectors)]
                    for start in range(0, len(points), 100):
                        self.client.upsert(self.collection, points[start:start + 100], wait=True)
                    self.store.activate(bid, path.name, fingerprint, version, generation, evidence, warnings)
                    report["indexed"].append(path.name)
                    report["warnings"].extend(warnings)
                    if old:
                        try:
                            self._remove_generation(old["generation"])
                        except Exception:
                            # Activated evidence must survive an optional stale-vector cleanup failure.
                            report["warnings"].append(f"{path.name}: stale vector cleanup deferred")
                except Exception as exc:
                    report["errors"].append({"file": path.name, "error": f"{type(exc).__name__}: {exc}"})
                    try:
                        self._remove_generation(generation)
                    except Exception:
                        report["warnings"].append(f"{path.name}: failed generation cleanup deferred")
            existing = {p.name for p in paths}
            for file, old in manifest.items():
                if file not in existing:
                    self.store.remove(bid, file)
                    self._remove_generation(old["generation"])
                    report["deleted"].append(file)
        report["status"] = "partial" if report["errors"] or report["warnings"] else "complete"
        return report

    def _remove_generation(self, generation):
        if self.client.collection_exists(self.collection):
            self.client.delete(self.collection, models.FilterSelector(filter=models.Filter(must=[models.FieldCondition(key="generation", match=models.MatchValue(value=generation))])))

    def search(self, request: SearchRequest) -> list[Evidence]:
        with self.lock:
            evidence = [e for e in self.store.evidence(request.bid_ids)
                        if (not request.doc_types or e.doc_type in request.doc_types)
                        and (not request.addendum_numbers or e.addendum_number in request.addendum_numbers)]
            if not evidence:
                return []
            if not self.client.collection_exists(self.collection):
                raise ValueError("Embedding model changed: re-index the corpus with this model before searching")
            by_id = {e.id: e for e in evidence}
            must = [models.FieldCondition(key="generation", match=models.MatchAny(any=self.store.active_generations()))]
            for key, values in [("bid_id", request.bid_ids), ("doc_type", request.doc_types), ("addendum_number", request.addendum_numbers)]:
                if values:
                    must.append(models.FieldCondition(key=key, match=models.MatchAny(any=values)))
            rankings = []
            for query in dict.fromkeys([request.query, expand(request.query)]):
                vec = self.embedder.encode([query], normalize_embeddings=True, show_progress_bar=False)[0]
                hits = self.client.query_points(self.collection, query=np.asarray(vec).tolist(),
                                                query_filter=models.Filter(must=must), limit=30).points
                rankings.append([h.payload["id"] for h in hits if h.payload["id"] in by_id])
                if request.mode != "dense":
                    bm25 = BM25Okapi([tokenize(e.text + " " + e.heading) for e in evidence], epsilon=.25)
                    scores = bm25.get_scores(tokenize(query))
                    # Zero-score documents are not keyword hits.
                    rankings.append([evidence[i].id for i in np.argsort(-scores)[:30] if scores[i] > 0])
            ids, scores = rrf(rankings)
            candidates = ids[:30]
            if request.mode == "rerank" and candidates:
                ranked = self.reranker.predict([(request.query, by_id[key].text) for key in candidates])
                candidates = [key for key, score in sorted(zip(candidates, ranked), key=lambda p: (-float(p[1]), p[0]))]
                scores = dict(zip(ids[:30], map(float, ranked)))
            return [by_id[key].model_copy(update={"score": scores[key]}) for key in candidates[:request.top_k]]
