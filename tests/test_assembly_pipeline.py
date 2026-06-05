import unittest

from tests._helpers import load_assembly_fixture

from modules.assembly.ir import AssemblyMeta, AssemblyResult
from modules.assembly.normalize_filter import NormalizeFilter
from modules.assembly.service import DocumentAssembler
from modules.assembly.structure import StructureAssembler
from modules.assembly.validator import AssemblyValidator


class AssemblyServiceContractTests(unittest.TestCase):
    def test_document_assembler_merges_layout_and_table_outputs(self):
        result = DocumentAssembler().build(load_assembly_fixture("table_caption_note"))

        self.assertEqual(result.metadata.stage, "validated")
        self.assertEqual(result.metadata.adapter, "merged")
        self.assertEqual(result.metadata.source, "raw")
        self.assertEqual(len(result.ordered_elements), 4)
        self.assertEqual([element.id for element in result.ordered_elements], ["intro_1", "table_1", "cap_1", "note_1"])
        self.assertEqual(len(result.document.table_refs), 1)
        self.assertEqual(len(result.document.note_refs), 1)
        self.assertEqual(result.document.note_refs[0].note_id, "note_1")
        self.assertEqual(result.document.table_refs[0].caption_id, "cap_1")
        self.assertEqual(result.document.table_refs[0].note_ids, ["note_1"])

        serialized = result.to_dict()
        self.assertEqual(serialized["document"]["table_refs"][0]["table_id"], "table_1")
        self.assertEqual(serialized["metadata"]["adapter"], "merged")

    def test_document_assembler_build_from_outputs_links_markdown_table_to_layout_ref(self):
        fixture = load_assembly_fixture("layout_markdown_link")

        result = DocumentAssembler().build_from_outputs(
            fixture["layout_output"],
            fixture["table_markdown"],
        )

        self.assertEqual(result.metadata.stage, "validated")
        self.assertEqual(result.metadata.adapter, "merged")
        self.assertEqual(len(result.ordered_elements), 1)
        self.assertEqual([element.id for element in result.ordered_elements], ["p1_table_7"])
        self.assertEqual(len(result.document.table_refs), 1)

        table_ref = result.document.table_refs[0]
        self.assertEqual(table_ref.table_id, "p1_table_7")
        self.assertEqual(table_ref.page, 1)
        self.assertEqual(table_ref.bbox, (120.0, 150.0, 880.0, 500.0))
        self.assertEqual(table_ref.metadata["content_format"], "markdown")
        self.assertEqual(table_ref.metadata["crop_path"], "data/output\\sample_layout.pdf\\crops\\p1_table_7.png")
        self.assertEqual(table_ref.metadata["link_strategy"], "document_order")
        self.assertIn("|", table_ref.metadata["markdown"])


class AssemblyStageContractTests(unittest.TestCase):
    def test_normalize_filter_requires_adapter_seed_result(self):
        with self.assertRaises(TypeError):
            NormalizeFilter.apply({"not": "assembly"})

        with self.assertRaises(ValueError):
            NormalizeFilter.apply(AssemblyResult(metadata=AssemblyMeta(stage="normalized")))

    def test_structure_assembler_requires_normalized_result(self):
        with self.assertRaises(TypeError):
            StructureAssembler.apply({"not": "assembly"})

        with self.assertRaises(ValueError):
            StructureAssembler.apply(AssemblyResult(metadata=AssemblyMeta(stage="adapter_seed")))

    def test_validator_requires_structure_assembled_result(self):
        with self.assertRaises(TypeError):
            AssemblyValidator.apply({"not": "assembly"})

        with self.assertRaises(ValueError):
            AssemblyValidator.apply(AssemblyResult(metadata=AssemblyMeta(stage="normalized")))


if __name__ == "__main__":
    unittest.main()
