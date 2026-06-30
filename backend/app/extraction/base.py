"""Extraction provider interface (see §11)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class FieldResult:
    value: Optional[str]
    confidence: float = 0.0
    page: Optional[int] = None
    bbox: Optional[dict] = None


@dataclass
class ExtractionResult:
    raw_text: str = ""
    fields: dict[str, FieldResult] = field(default_factory=dict)
    line_items: list[dict[str, Any]] = field(default_factory=list)
    provider: str = "mock"


class InvoiceExtractionProvider(ABC):
    name: str = "base"

    @abstractmethod
    def extract(self, file_path: str, mime_type: str) -> ExtractionResult:
        """Run extraction and return normalized result."""
        raise NotImplementedError