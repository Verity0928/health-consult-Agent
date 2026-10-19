import json
from pathlib import Path

from pydantic import ValidationError

from app.schemas import KBEntry

DEFAULT_KB_DATA_DIR = Path(__file__).parent / "data"


def load_knowledge_base(data_dir: Path) -> list[KBEntry]:
    entries: list[KBEntry] = []
    for path in sorted(data_dir.glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        try:
            entries.extend(KBEntry.model_validate(item) for item in raw)
        except ValidationError as exc:
            raise ValueError(f"{path.name}: {exc}") from exc
    return entries
