"""Inspect normalized source blocks without downloading models or calling an LLM."""
import json
from pathlib import Path
from rfp_intelligence.ingestion.parsers import parse


def main():
    output = Path(".data/audit")
    output.mkdir(parents=True, exist_ok=True)
    report = []
    for folder in [Path("Bid1"), Path("Bid2")]:
        for file in sorted(folder.iterdir()):
            blocks, warnings = parse(file, folder.name)
            report.append({"bid": folder.name, "file": file.name, "blocks": len(blocks),
                           "tables": sum("table[" in e.locator for e in blocks), "warnings": warnings})
            text = "\n\n".join(f"PAGE {e.page}, LOCATOR {e.locator}\n{e.text}" for e in blocks)
            (output / (folder.name + "_" + file.stem[:75] + ".txt")).write_text(text, encoding="utf-8")
    Path("outputs").mkdir(exist_ok=True)
    Path("outputs/corpus_audit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
