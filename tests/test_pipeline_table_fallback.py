import os
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from tests import _helpers  # noqa: F401


class DummyComponent:
    pass


if "torch" not in sys.modules:
    torch_stub = types.ModuleType("torch")
    torch_stub.float16 = object()
    torch_stub.cuda = types.SimpleNamespace(
        is_available=lambda: False,
        empty_cache=lambda: None,
    )
    sys.modules["torch"] = torch_stub

if "dotenv" not in sys.modules:
    dotenv_stub = types.ModuleType("dotenv")
    dotenv_stub.load_dotenv = lambda *args, **kwargs: None
    sys.modules["dotenv"] = dotenv_stub

for module_name, class_name in (
    ("modules.ingestion", "FilePreProcessor"),
    ("modules.vision_engine", "LayoutAnalyzer"),
    ("modules.text_extractor", "TextExtractor"),
):
    if module_name not in sys.modules:
        module_stub = types.ModuleType(module_name)
        setattr(module_stub, class_name, DummyComponent)
        sys.modules[module_name] = module_stub

from pipeline import DocumentToMarkdownPipeline


class DummyTableExtractor:
    def __init__(self):
        self.calls = []

    def extract_table(self, image_path):
        self.calls.append(image_path)
        return "| should | not | run |"


class PipelineTableFallbackTests(unittest.TestCase):
    def test_force_table_extraction_fallback_skips_table_extractor_call(self):
        table_extractor = DummyTableExtractor()
        layout_result = {
            "pages": [
                {
                    "page_num": 2,
                    "elements": [
                        {
                            "id": 7,
                            "type": "Table",
                            "bbox": [10, 20, 300, 160],
                            "crop_path": "data/temp/table.png",
                        }
                    ],
                }
            ]
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(
                os.environ,
                {
                    "TABLE_EXTRACTION_FORCE_FALLBACK": "true",
                    "LLM_ENRICHMENT_MODE": "baseline",
                },
                clear=False,
            ):
                pipeline = DocumentToMarkdownPipeline(
                    preprocessor=DummyComponent(),
                    vision_engine=DummyComponent(),
                    text_extractor=DummyComponent(),
                    table_extractor=table_extractor,
                    assembler=DummyComponent(),
                    renderer=DummyComponent(),
                    semantic_enricher=DummyComponent(),
                    content_enricher=DummyComponent(),
                    project_root=temp_dir,
                )

        table_results = pipeline._build_table_results(layout_result)

        self.assertEqual(table_extractor.calls, [])
        self.assertEqual(len(table_results), 1)
        self.assertEqual(table_results[0]["table_id"], "p2_table_7")
        self.assertEqual(table_results[0]["extraction_error"], "TABLE_EXTRACTION_FORCE_FALLBACK=true")
        self.assertNotIn("markdown", table_results[0])


if __name__ == "__main__":
    unittest.main()
