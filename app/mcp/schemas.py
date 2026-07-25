from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal


@dataclass
class WebFinding:
    title: str
    url: str
    snippet: str
    provider: Literal["wikipedia", "duckduckgo"]
    retrieved_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_source_dict(self, index: int) -> dict:
        return {
            "source_type": "web",
            "chunk_id": None,
            "content": self.snippet,
            "page": None,
            "bboxes": None,
            "page_width": None,
            "page_height": None,
            "url": self.url,
            "title": self.title,
            "provider": self.provider,
            "citation_label": f"W{index}",
        }
