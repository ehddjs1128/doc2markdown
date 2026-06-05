import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
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
from modules.assembly.ir import AssemblyMeta, AssemblyResult, AssembledDocument
from modules.assembly.service import AssemblyBuildTrace


class DummyTableExtractor:
    def __init__(self):
        self.calls = []

    def extract_table(self, image_path):
        self.calls.append(image_path)
        return "| should | not | run |"


class FakePreprocessor:
    def process(self, file_path):
        return {"pages": [], "file_path": file_path}


class FakeVisionEngine:
    def analyze(self, raw_pages):
        return {"pages": [], "raw_pages": raw_pages}


class FakeTextExtractor:
    def extract_text(self, layout_result, file_path):
        return {"pages": [], "file_path": file_path, "layout_result": layout_result}


class FakeAssembler:
    def __init__(self):
        self.calls = []

    def build_from_outputs_with_trace(
        self,
        layout_result,
        table_result,
        *,
        semantic_enricher,
        content_enricher,
    ):
        self.calls.append(
            {
                "layout_result": layout_result,
                "table_result": table_result,
                "semantic_enricher": semantic_enricher,
                "content_enricher": content_enricher,
            }
        )
        assembly_result = AssemblyResult(
            document=AssembledDocument(),
            metadata=AssemblyMeta(stage="validated"),
        )
        return AssemblyBuildTrace(result=assembly_result, stages={"validated": assembly_result})


class FakeRenderer:
    def __init__(self):
        self.render_inputs = []

    def render(self, assembly_result):
        self.render_inputs.append(assembly_result)
        return {"markdown": "# ok"}

    def save(self, markdown_result, output_dir):
        return {"markdown_path": str(Path(output_dir) / "output.md")}


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

    def test_disabled_table_extraction_skips_table_extractor_call(self):
        table_extractor = DummyTableExtractor()
        layout_result = {
            "pages": [
                {
                    "page_num": 3,
                    "elements": [
                        {
                            "id": 8,
                            "type": "Table",
                            "bbox": [15, 25, 320, 180],
                            "crop_path": "data/temp/disabled-table.png",
                        }
                    ],
                }
            ]
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(
                os.environ,
                {
                    "TABLE_EXTRACTION_ENABLED": "false",
                    "TABLE_EXTRACTION_FORCE_FALLBACK": "false",
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
        self.assertEqual(table_results[0]["table_id"], "p3_table_8")
        self.assertEqual(table_results[0]["crop_path"], "data/temp/disabled-table.png")
        self.assertEqual(table_results[0]["extraction_error"], "TABLE_EXTRACTION_ENABLED=false")
        self.assertNotIn("markdown", table_results[0])

    def test_worker_timeout_seconds_uses_environment_override(self):
        from modules.table_extractor import TableExtractor

        with patch.dict(
            os.environ,
            {"TABLE_EXTRACTION_WORKER_TIMEOUT_SECONDS": "12"},
            clear=False,
        ):
            table_extractor = TableExtractor()

        self.assertEqual(table_extractor.timeout_seconds, 12)

    def test_run_preserves_result_shape_with_trace_assembly(self):
        table_extractor = DummyTableExtractor()
        assembler = FakeAssembler()
        renderer = FakeRenderer()
        semantic_enricher = DummyComponent()
        content_enricher = DummyComponent()

        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "input.pdf"
            input_path.write_text("fake pdf", encoding="utf-8")
            with patch.dict(
                os.environ,
                {"LLM_ENRICHMENT_MODE": "baseline"},
                clear=False,
            ):
                pipeline = DocumentToMarkdownPipeline(
                    preprocessor=FakePreprocessor(),
                    vision_engine=FakeVisionEngine(),
                    text_extractor=FakeTextExtractor(),
                    table_extractor=table_extractor,
                    assembler=assembler,
                    renderer=renderer,
                    semantic_enricher=semantic_enricher,
                    content_enricher=content_enricher,
                    project_root=temp_dir,
                )
                result = pipeline.run(str(input_path))

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["assembly_result"]["metadata"]["stage"], "validated")
        self.assertEqual(result["markdown_result"]["markdown"], "# ok")
        self.assertIn("markdown_path", result["saved_paths"])
        self.assertEqual(len(assembler.calls), 1)
        self.assertIs(assembler.calls[0]["semantic_enricher"], semantic_enricher)
        self.assertIs(assembler.calls[0]["content_enricher"], content_enricher)


if __name__ == "__main__":
    unittest.main()
