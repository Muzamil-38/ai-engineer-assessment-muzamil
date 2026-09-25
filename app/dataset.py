from pathlib import Path

from app.schemas import Source

DATASET_PATH = Path(__file__).resolve().parent.parent / "data" / "cristiano_ronaldo.md"


def load_sections(path: Path = DATASET_PATH) -> dict[str, Source]:
    text = path.read_text(encoding="utf-8")
    header = text.split("\n## ", 1)[0]
    source_url = next(
        line.removeprefix("Source: ") for line in header.splitlines() if line.startswith("Source: ")
    )
    sections = {}
    for block in text.split("\n## ")[1:]:
        heading, content = block.split("\n", 1)
        section_id, title = heading.split(" | ", 1)
        section_url = source_url
        if content.startswith("Source: "):
            source_line, content = content.split("\n", 1)
            section_url = source_line.removeprefix("Source: ").strip()
        sections[section_id] = Source(
            id=f"cr7:{section_id}",
            type="dataset",
            title=f"Cristiano Ronaldo — {title}",
            location=section_url,
            content=content.strip(),
        )
    if not sections:
        raise ValueError("The Ronaldo dataset has no sections")
    return sections
