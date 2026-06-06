from __future__ import annotations

"""Markdown 렌더링 중 반복 조회할 문맥 정보."""

from dataclasses import dataclass, field

from modules.assembly.ir import AssemblyElement, AssemblyResult, NoteRef
from modules.rendering.markdown.text import normalize_single_line_text


@dataclass
class RenderContext:
    ordered_element_map: dict[str, AssemblyElement] = field(default_factory=dict)
    note_ref_map: dict[str, NoteRef] = field(default_factory=dict)
    target_note_map: dict[str, list[str]] = field(default_factory=dict)
    rendered_attached_note_ids: set[str] = field(default_factory=set)

    def lookup_caption_text(self, caption_id: str | None) -> str:
        """caption_id에 해당하는 caption text를 찾아 한 줄 텍스트로 정리한다."""
        if not caption_id:
            return ""

        caption_element = self.ordered_element_map.get(caption_id)
        if not isinstance(caption_element, AssemblyElement):
            return ""

        return normalize_single_line_text(caption_element.text)

    def resolve_attached_notes(
        self,
        target_id: str,
        preferred_note_ids: list[str],
    ) -> list[NoteRef]:
        """target_id에 붙은 note를 중복 없이 순서대로 모은다."""
        resolved_note_ids: list[str] = []

        for note_id in preferred_note_ids:
            if isinstance(note_id, str) and note_id not in resolved_note_ids:
                resolved_note_ids.append(note_id)

        for note_id in self.target_note_map.get(target_id, []):
            if note_id not in resolved_note_ids:
                resolved_note_ids.append(note_id)

        resolved_notes: list[NoteRef] = []
        for note_id in resolved_note_ids:
            note_ref = self.note_ref_map.get(note_id)
            if isinstance(note_ref, NoteRef):
                resolved_notes.append(note_ref)

        return resolved_notes

    def has_rendered_note(self, note_id: str) -> bool:
        """이미 출력한 attached note인지 확인한다."""
        return note_id in self.rendered_attached_note_ids

    def mark_note_rendered(self, note_id: str) -> None:
        """attached note가 중복 출력되지 않도록 출력 여부를 기록한다."""
        self.rendered_attached_note_ids.add(note_id)


def build_render_context(result: AssemblyResult) -> RenderContext:
    """AssemblyResult에서 렌더링용 조회 map을 만든다."""
    note_ref_map = {
        note_ref.note_id: note_ref
        for note_ref in result.document.note_refs
    }
    target_note_map: dict[str, list[str]] = {}
    for note_ref in result.document.note_refs:
        if not note_ref.target_id:
            continue
        target_note_map.setdefault(note_ref.target_id, []).append(note_ref.note_id)

    return RenderContext(
        ordered_element_map={
            element.id: element
            for element in result.ordered_elements
        },
        note_ref_map=note_ref_map,
        target_note_map=target_note_map,
    )
