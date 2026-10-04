import json
import time
from pathlib import Path
from datetime import datetime, timezone


class Trace:
    def __init__(self, output: Path, run_id: str):
        output.mkdir(parents=True, exist_ok=True)
        self.path = output / f"{run_id}.jsonl"
        self.start = time.perf_counter()

    def event(self, agent, event, data):
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"timestamp": datetime.now(timezone.utc).isoformat(),
                "agent": agent, "event": event, "elapsed_ms": round((time.perf_counter() - self.start) * 1000),
                "data": data}, ensure_ascii=False, default=str) + "\n")
