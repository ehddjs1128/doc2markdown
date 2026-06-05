from __future__ import annotations

import importlib
import json
import sys
import unittest
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
FIXTURE_DIR = ROOT_DIR / "tests" / "fixtures" / "assembly"


def bootstrap_src_path() -> None:
    src_path = str(SRC_DIR)
    if src_path not in sys.path:
        sys.path.insert(0, src_path)


bootstrap_src_path()


def load_assembly_fixture(name: str) -> Any:
    with (FIXTURE_DIR / f"{name}.json").open("r", encoding="utf-8") as file:
        return json.load(file)


class FakeLLMClient:
    def __init__(self, responses: dict[str, Any]):
        self.responses = responses
        self.calls: list[tuple[str, Any]] = []

    @property
    def model_id(self) -> str:
        return "fake-local-llm"

    def generate_json(self, task: str, payload: Any) -> Any:
        self.calls.append((task, payload))
        response = self.responses.get(task, {})
        if isinstance(response, Exception):
            raise response
        return response


def import_or_skip(module_name: str, reason: str | None = None) -> Any:
    try:
        return importlib.import_module(module_name)
    except ImportError as error:
        skip_reason = reason or f"{module_name} is not installed"
        raise unittest.SkipTest(skip_reason) from error
