import unittest

from tests import _helpers  # noqa: F401

from modules.assembly.service import DocumentAssembler


def build_layout_payload(
    elements,
    *,
    file_name: str = "mixed_layout_case.pdf",
    width: int = 3000,
    height: int = 2895,
):
    return {
        "layout_output": {
            "file_name": file_name,
            "total_pages": 1,
            "pages": [
                {
                    "page_num": 1,
                    "width": width,
                    "height": height,
                    "elements": elements,
                }
            ],
        },
        "table_output": [],
    }


class AssemblyStructureReadingOrderTests(unittest.TestCase):
    def test_document_assembler_preserves_upstream_order_when_top_block_crosses_boundary(self):
        raw = build_layout_payload(
            [
                {
                    "id": 1,
                    "type": "Text",
                    "bbox": [148.68, 148.62, 1524.73, 1094.45],
                    "confidence": 0.95,
                    "text": "Left intro block that slightly crosses the inferred boundary.",
                },
                {
                    "id": 2,
                    "type": "Text",
                    "bbox": [147.62, 1177.04, 907.44, 1475.25],
                    "confidence": 0.95,
                    "text": "Left lower block",
                },
                {
                    "id": 13,
                    "type": "Section-header",
                    "bbox": [1796.69, 149.93, 2126.31, 234.29],
                    "confidence": 0.95,
                    "text": "Right heading",
                },
                {
                    "id": 15,
                    "type": "Text",
                    "bbox": [1801.04, 1917.92, 3331.48, 2190.83],
                    "confidence": 0.95,
                    "text": "Right body block",
                },
            ],
            width=3509,
            file_name="boundary_case.pdf",
        )

        result = DocumentAssembler().build_structure(raw)

        self.assertEqual(
            [(element.id, element.reading_order) for element in result.ordered_elements[:4]],
            [
                ("p1_text_1", 1),
                ("p1_text_2", 2),
                ("p1_heading_13", 3),
                ("p1_text_15", 4),
            ],
        )

    def test_document_assembler_preserves_upstream_order_for_wide_left_block(self):
        raw = build_layout_payload(
            [
                {
                    "id": 1,
                    "type": "Text",
                    "bbox": [148.68, 148.62, 1524.73, 1094.45],
                    "confidence": 0.95,
                    "text": "Left intro block that should remain in column 1.",
                },
                {
                    "id": 2,
                    "type": "Text",
                    "bbox": [147.62, 1177.04, 907.44, 1475.25],
                    "confidence": 0.95,
                    "text": "Left lower block",
                },
                {
                    "id": 13,
                    "type": "Section-header",
                    "bbox": [1796.69, 149.93, 2126.31, 234.29],
                    "confidence": 0.95,
                    "text": "Right heading",
                },
                {
                    "id": 15,
                    "type": "Text",
                    "bbox": [1801.04, 1917.92, 3331.48, 2190.83],
                    "confidence": 0.95,
                    "text": "Right body block",
                },
            ],
            file_name="gutter_boundary_case.pdf",
        )

        result = DocumentAssembler().build_structure(raw)

        self.assertEqual(
            [(element.id, element.reading_order) for element in result.ordered_elements[:4]],
            [
                ("p1_text_1", 1),
                ("p1_text_2", 2),
                ("p1_heading_13", 3),
                ("p1_text_15", 4),
            ],
        )

    def test_document_assembler_preserves_upstream_order_for_spanning_intro(self):
        raw = build_layout_payload(
            [
                {
                    "id": 1,
                    "type": "Text",
                    "bbox": [120.0, 120.0, 2880.0, 360.0],
                    "confidence": 0.98,
                    "text": "Top intro spanning block",
                },
                {
                    "id": 2,
                    "type": "Text",
                    "bbox": [140.0, 520.0, 1100.0, 760.0],
                    "confidence": 0.98,
                    "text": "Left column first block",
                },
                {
                    "id": 3,
                    "type": "Text",
                    "bbox": [140.0, 860.0, 1100.0, 1120.0],
                    "confidence": 0.98,
                    "text": "Left column second block",
                },
                {
                    "id": 4,
                    "type": "Text",
                    "bbox": [1700.0, 540.0, 2680.0, 800.0],
                    "confidence": 0.98,
                    "text": "Right column first block",
                },
                {
                    "id": 5,
                    "type": "Text",
                    "bbox": [1700.0, 900.0, 2680.0, 1160.0],
                    "confidence": 0.98,
                    "text": "Right column second block",
                },
            ],
            file_name="top_spanning_then_two_columns.pdf",
        )

        result = DocumentAssembler().build_structure(raw)

        self.assertEqual(
            [(element.id, element.reading_order) for element in result.ordered_elements[:5]],
            [
                ("p1_text_1", 1),
                ("p1_text_2", 2),
                ("p1_text_3", 3),
                ("p1_text_4", 4),
                ("p1_text_5", 5),
            ],
        )

    def test_document_assembler_preserves_upstream_order_around_midpage_spanning_block(self):
        raw = build_layout_payload(
            [
                {
                    "id": 1,
                    "type": "Text",
                    "bbox": [140.0, 180.0, 1100.0, 430.0],
                    "confidence": 0.98,
                    "text": "Top left block",
                },
                {
                    "id": 2,
                    "type": "Text",
                    "bbox": [1700.0, 200.0, 2680.0, 450.0],
                    "confidence": 0.98,
                    "text": "Top right block",
                },
                {
                    "id": 3,
                    "type": "Text",
                    "bbox": [130.0, 760.0, 2860.0, 980.0],
                    "confidence": 0.98,
                    "text": "Middle spanning separator",
                },
                {
                    "id": 4,
                    "type": "Text",
                    "bbox": [140.0, 1220.0, 1100.0, 1470.0],
                    "confidence": 0.98,
                    "text": "Bottom left block",
                },
                {
                    "id": 5,
                    "type": "Text",
                    "bbox": [1700.0, 1240.0, 2680.0, 1490.0],
                    "confidence": 0.98,
                    "text": "Bottom right block",
                },
            ],
            file_name="two_columns_spanning_two_columns.pdf",
        )

        result = DocumentAssembler().build_structure(raw)

        self.assertEqual(
            [(element.id, element.reading_order) for element in result.ordered_elements[:5]],
            [
                ("p1_text_1", 1),
                ("p1_text_2", 2),
                ("p1_text_3", 3),
                ("p1_text_4", 4),
                ("p1_text_5", 5),
            ],
        )


if __name__ == "__main__":
    unittest.main()
