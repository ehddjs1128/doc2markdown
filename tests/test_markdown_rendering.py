import os
from pathlib import Path
import tempfile
import unittest

from tests import _helpers  # noqa: F401

from modules.assembly.ir import (
    AssembledDocument,
    AssemblyElement,
    AssemblyMeta,
    AssemblyResult,
    FigureRef,
    NoteRef,
    ParagraphGroup,
    SectionNode,
    TableRef,
)
from modules.rendering.ir import MarkdownRenderResult
from modules.rendering.service import MarkdownRenderer


class MarkdownRenderingTests(unittest.TestCase):
    def test_body_text_starting_with_hash_is_escaped_without_affecting_real_heading(self):
        section = SectionNode(
            id="section_1",
            level=1,
            title="Actual heading",
            heading_block_id="h1",
        )
        paragraph = ParagraphGroup(
            id="paragraph_1",
            block_ids=["p1"],
            text="# literal hash text",
            source_block_ids=["p1"],
        )
        result = AssemblyResult(
            document=AssembledDocument(
                children=[section, paragraph],
                sections=[section],
            ),
            metadata=AssemblyMeta(stage="validated"),
        )

        rendered = MarkdownRenderer().render(result)

        self.assertEqual(rendered.markdown, "# Actual heading\n\n\\# literal hash text")
        self.assertEqual(rendered.warnings, [])

    def test_already_escaped_hash_text_is_not_double_escaped(self):
        paragraph = ParagraphGroup(
            id="paragraph_1",
            block_ids=["p1"],
            text="\\# already escaped",
            source_block_ids=["p1"],
        )
        result = AssemblyResult(
            document=AssembledDocument(children=[paragraph]),
            metadata=AssemblyMeta(stage="validated"),
        )

        rendered = MarkdownRenderer().render(result)

        self.assertEqual(rendered.markdown, "\\# already escaped")

    def test_body_text_starting_with_blockquote_marker_is_escaped(self):
        paragraph = ParagraphGroup(
            id="paragraph_1",
            block_ids=["p1"],
            text="> quoted looking text",
            source_block_ids=["p1"],
        )
        result = AssemblyResult(
            document=AssembledDocument(children=[paragraph]),
            metadata=AssemblyMeta(stage="validated"),
        )

        rendered = MarkdownRenderer().render(result)

        self.assertEqual(rendered.markdown, "\\> quoted looking text")

    def test_thematic_break_like_text_is_escaped(self):
        for raw_text, escaped_text in [
            ("---", "\\---"),
            ("***", "\\***"),
            ("___", "\\___"),
            ("- - -", "\\- - -"),
        ]:
            with self.subTest(raw_text=raw_text):
                paragraph = ParagraphGroup(
                    id="paragraph_1",
                    block_ids=["p1"],
                    text=raw_text,
                    source_block_ids=["p1"],
                )
                result = AssemblyResult(
                    document=AssembledDocument(children=[paragraph]),
                    metadata=AssemblyMeta(stage="validated"),
                )

                rendered = MarkdownRenderer().render(result)

                self.assertEqual(rendered.markdown, escaped_text)

    def test_render_rejects_non_validated_stage(self):
        result = AssemblyResult(
            document=AssembledDocument(),
            metadata=AssemblyMeta(stage="structure_assembled"),
        )

        with self.assertRaises(ValueError):
            MarkdownRenderer().render(result)

    def test_render_accepts_serialized_assembly_result(self):
        paragraph = ParagraphGroup(
            id="paragraph_1",
            block_ids=["p1"],
            text="serialized paragraph",
            source_block_ids=["p1"],
        )
        result = AssemblyResult(
            document=AssembledDocument(children=[paragraph]),
            metadata=AssemblyMeta(stage="validated"),
        )

        rendered = MarkdownRenderer().render(result.to_dict())

        self.assertEqual(rendered.markdown, "serialized paragraph")

    def test_static_render_call_keeps_public_contract(self):
        paragraph = ParagraphGroup(
            id="paragraph_1",
            block_ids=["p1"],
            text="static call paragraph",
            source_block_ids=["p1"],
        )
        result = AssemblyResult(
            document=AssembledDocument(children=[paragraph]),
            metadata=AssemblyMeta(stage="validated"),
        )

        rendered = MarkdownRenderer.render(result)

        self.assertEqual(rendered.markdown, "static call paragraph")

    def test_table_markdown_renders_caption_and_attached_note_once(self):
        caption = AssemblyElement(
            id="caption_1",
            page=1,
            kind="caption",
            text="Table 1 caption",
        )
        table = TableRef(
            table_id="table_1",
            page=1,
            caption_id="caption_1",
            note_ids=["note_1"],
            metadata={"markdown": "| A |\n| --- |\n| 1 |"},
        )
        note = NoteRef(
            note_id="note_1",
            page=1,
            text="attached note",
            target_id="table_1",
        )
        result = AssemblyResult(
            ordered_elements=[caption],
            document=AssembledDocument(
                children=[table, note],
                table_refs=[table],
                note_refs=[note],
            ),
            metadata=AssemblyMeta(stage="validated"),
        )

        rendered = MarkdownRenderer().render(result)

        self.assertEqual(
            rendered.markdown,
            "| A |\n| --- |\n| 1 |\n\n*Table 1 caption*\n\nattached note",
        )
        self.assertEqual(rendered.warnings, [])

    def test_table_fallback_and_placeholder_warnings_are_reported(self):
        crop_table = TableRef(
            table_id="table_crop",
            page=1,
            metadata={"crop_path": "assets\\table.png"},
        )
        missing_table = TableRef(table_id="table_missing", page=1)
        result = AssemblyResult(
            document=AssembledDocument(
                children=[crop_table, missing_table],
                table_refs=[crop_table, missing_table],
            ),
            metadata=AssemblyMeta(stage="validated"),
        )

        rendered = MarkdownRenderer().render(result)

        self.assertIn("![Table table_crop](assets/table.png)", rendered.markdown)
        self.assertIn("[TABLE PLACEHOLDER: table_missing]", rendered.markdown)
        self.assertEqual(
            [warning.code for warning in rendered.warnings],
            ["table_crop_fallback", "table_placeholder"],
        )
        self.assertEqual(rendered.stats.table_fallback_count, 1)
        self.assertEqual(rendered.stats.placeholder_count, 1)

    def test_figure_asset_and_placeholder_warning_are_reported(self):
        figure = FigureRef(
            figure_id="figure_1",
            page=1,
            asset_path="figures\\figure.png",
        )
        missing_figure = FigureRef(figure_id="figure_missing", page=1)
        result = AssemblyResult(
            document=AssembledDocument(
                children=[figure, missing_figure],
                figure_refs=[figure, missing_figure],
            ),
            metadata=AssemblyMeta(stage="validated"),
        )

        rendered = MarkdownRenderer().render(result)

        self.assertIn("![Figure figure_1](figures/figure.png)", rendered.markdown)
        self.assertIn("[FIGURE PLACEHOLDER: figure_missing]", rendered.markdown)
        self.assertEqual([warning.code for warning in rendered.warnings], ["figure_placeholder"])
        self.assertEqual(rendered.stats.placeholder_count, 1)

    def test_save_rewrites_image_paths_relative_to_markdown_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            asset_dir = temp_path / "assets"
            asset_dir.mkdir()
            asset_path = asset_dir / "figure.png"
            asset_path.write_bytes(b"image")

            render_result = MarkdownRenderResult(
                markdown=f"![Figure figure_1]({asset_path})"
            )
            saved_paths = MarkdownRenderer().save(
                render_result,
                output_dir=temp_path / "out",
            )

            markdown_path = Path(saved_paths["markdown_path"])
            saved_markdown = markdown_path.read_text(encoding="utf-8")
            expected_path = Path(
                os.path.relpath(asset_path.resolve(), markdown_path.parent.resolve())
            ).as_posix()
            self.assertEqual(saved_markdown, f"![Figure figure_1]({expected_path})")


if __name__ == "__main__":
    unittest.main()
