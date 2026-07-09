"""Common provider interface: one async method, JSON in / JSON out.

Providers raise on failure; retry policy lives in the pipeline (one place),
on top of whatever the vendor SDK already retries (429/5xx).
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod


class Provider(ABC):
    name: str

    @abstractmethod
    async def complete_json(self, system: str, user: str, schema: dict) -> dict:
        """Run one completion forced to match `schema`; return the parsed object."""


def parse_json_strict(text: str) -> dict:
    """Parse model output as JSON, tolerating markdown code fences."""
    stripped = text.strip()
    if stripped.startswith("```"):
        first_newline = stripped.index("\n")
        stripped = stripped[first_newline + 1 :]
        if stripped.rstrip().endswith("```"):
            stripped = stripped.rstrip()[:-3]
    return json.loads(stripped)
