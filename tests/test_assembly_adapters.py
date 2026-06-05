import unittest

from tests._helpers import load_assembly_fixture

from modules.assembly.adapters import from_layout_output, from_table_output


class LayoutAdapterContractTests(unittest.TestCase):
    def test_single_column_fixture_is_normalized_into_layout_ir(self):
        result = from_layout_output(load_assembly_fixture("single_column"))

        self.assertEqual(result.metadata.stage, "adapter_seed")
        self.assertEqual(result.metadata.adapter, "layout")
        self.assertEqual(result.metadata.source, "raw")
        self.assertEqual(len(result.ordered_elements), 4)
        self.assertEqual([element.kind for element in result.ordered_elements], ["heading", "text", "text", "list_item"])
        self.assertEqual(result.document.title_candidate, "Document Title")
        self.assertEqual(result.document.title_source_block_ids, ["h1"])
        self.assertEqual(len(result.page_stats), 1)
        self.assertEqual(result.page_stats[0].column_count, 1)
        self.assertEqual(result.warnings, [])

    def test_two_column_fixture_preserves_upstream_column_and_order_hints(self):
        result = from_layout_output(load_assembly_fixture("two_column"))

        self.assertEqual([element.column_id for element in result.ordered_elements], [1, 1, 2, 2])
        self.assertEqual([element.reading_order for element in result.ordered_elements], [1, 2, 3, 4])
        self.assertEqual(result.page_stats[0].column_count, 2)

    def test_heading_list_fixture_supports_direct_list_source_and_label_aliases(self):
        result = from_layout_output(load_assembly_fixture("heading_list"))

        self.assertEqual(result.metadata.source, "direct_list")
        self.assertEqual([element.kind for element in result.ordered_elements], ["heading", "list_item", "list_item", "text"])
        self.assertEqual(result.document.title_candidate, "Section A")
        self.assertEqual(result.document.title_source_block_ids, ["title_1"])

    def test_layout_adapter_emits_fallback_warnings_for_missing_id_and_page(self):
        result = from_layout_output([{"label": "text", "text": "Loose paragraph"}])
        warning_codes = [warning.code for warning in result.warnings]

        self.assertEqual(result.metadata.source, "direct_list")
        self.assertEqual(result.ordered_elements[0].id, "element_1")
        self.assertEqual(result.ordered_elements[0].page, 1)
        self.assertIn("layout_missing_id", warning_codes)
        self.assertIn("layout_missing_page", warning_codes)


class TableAdapterContractTests(unittest.TestCase):
    def test_table_adapter_keeps_minimum_table_reference_and_extra_metadata(self):
        raw = load_assembly_fixture("table_caption_note")["table_output"]

        result = from_table_output(raw)

        self.assertEqual(result.metadata.stage, "adapter_seed")
        self.assertEqual(result.metadata.adapter, "table")
        self.assertEqual(result.metadata.source, "raw")
        self.assertEqual(len(result.document.table_refs), 1)

        table_ref = result.document.table_refs[0]
        self.assertEqual(table_ref.table_id, "table_1")
        self.assertEqual(table_ref.page, 1)
        self.assertEqual(table_ref.caption_id, "cap_1")
        self.assertEqual(table_ref.note_ids, ["note_1"])
        self.assertEqual(table_ref.source_block_ids, ["table_1"])
        self.assertEqual(table_ref.metadata["rows"], 3)
        self.assertEqual(table_ref.metadata["columns"], 4)
        self.assertEqual(table_ref.metadata["parser"], "stub")

    def test_table_adapter_emits_fallback_warnings_for_missing_id_and_page(self):
        result = from_table_output([{"table_id": None}])
        warning_codes = [warning.code for warning in result.warnings]

        self.assertEqual(result.metadata.source, "direct_list")
        self.assertEqual(result.document.table_refs[0].table_id, "table_1")
        self.assertEqual(result.document.table_refs[0].page, 1)
        self.assertIn("table_missing_id", warning_codes)
        self.assertIn("table_missing_page", warning_codes)

    def test_table_adapter_converts_plain_markdown_string_into_seed_ref(self):
        result = from_table_output(load_assembly_fixture("markdown_table_seed")["table_markdown"])
        warning_codes = [warning.code for warning in result.warnings]

        self.assertEqual(result.metadata.stage, "adapter_seed")
        self.assertEqual(result.metadata.adapter, "table")
        self.assertEqual(result.metadata.source, "raw")
        self.assertEqual(len(result.document.table_refs), 1)

        table_ref = result.document.table_refs[0]
        self.assertEqual(table_ref.table_id, "table_1")
        self.assertEqual(table_ref.page, 1)
        self.assertEqual(table_ref.metadata["content_format"], "markdown")
        self.assertIn("|", table_ref.metadata["markdown"])
        self.assertIn("table_missing_id", warning_codes)
        self.assertIn("table_missing_page", warning_codes)

    def test_table_adapter_accepts_mixed_raw_and_markdown_entries_in_one_list(self):
        raw = [
            {
                "table_id": "table_raw_1",
                "page": 3,
                "bbox": [10, 20, 200, 120],
                "rows": 2,
                "columns": 2,
            },
            load_assembly_fixture("markdown_table_seed")["table_markdown"],
        ]

        result = from_table_output(raw)

        self.assertEqual(result.metadata.source, "direct_list")
        self.assertEqual(len(result.document.table_refs), 2)
        self.assertEqual(result.document.table_refs[0].table_id, "table_raw_1")
        self.assertEqual(result.document.table_refs[0].page, 3)
        self.assertEqual(result.document.table_refs[1].table_id, "table_2")
        self.assertEqual(result.document.table_refs[1].metadata["content_format"], "markdown")


if __name__ == "__main__":
    unittest.main()
