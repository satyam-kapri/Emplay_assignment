from pathlib import Path
import os
from dataclasses import dataclass
from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    data_dir: Path
    output_dir: Path
    data_root: Path
    embedding_model: str
    rerank_model: str
    llm_url: str
    llm_model: str
    llm_key: str
    timeout: float = 60
    concurrency: int = 3
    repair_attempts: int = 2
    search_mode: str = "hybrid"

    @classmethod
    def load(cls):
        load_dotenv()
        return cls(Path(os.getenv("RFP_DATA_DIR", ".data")),
                   Path(os.getenv("RFP_OUTPUT_DIR", "outputs")),
                   Path(os.getenv("RFP_DATA_ROOT", ".")).resolve(),
                   os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5"),
                   os.getenv("RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L6-v2"),
                   os.getenv("LLM_BASE_URL", ""), os.getenv("LLM_MODEL", ""),
                   os.getenv("LLM_API_KEY", ""), float(os.getenv("LLM_TIMEOUT", "60")),
                   max(1, int(os.getenv("RFP_CONCURRENCY", "3"))),
                   max(0, int(os.getenv("RFP_REPAIR_ATTEMPTS", "2"))), os.getenv("RFP_SEARCH_MODE", "hybrid"))

    def bid_path(self, path: str | Path) -> Path:
        resolved = Path(path).resolve()
        if not resolved.is_relative_to(self.data_root) or not resolved.is_dir():
            raise ValueError("Bid folder must exist inside RFP_DATA_ROOT")
        return resolved
