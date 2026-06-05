from __future__ import annotations

"""table 추출 출력을 Assembly IR의 table ref로 바꾼다."""

from typing import Any

from modules.assembly.adapter_helpers import (
    BBOX_KEYS,
    CAPTION_KEYS,
    NOTE_KEYS,
    PAGE_NUMBER_KEYS,
    SOURCE_BLOCK_IDS_KEYS,
    TABLE_CONTAINER_KEYS,
    TABLE_ID_KEYS,
    TABLE_LIST_KEYS,
    TABLE_MARKDOWN_KEYS,
    WARNING_TABLE_MISSING_ID,
    WARNING_TABLE_MISSING_PAGE,
    _build_adapter_metadata,
    _coerce_list,
    _extract_metadata,
    _extract_source_block_ids,
    _has_layout_shape,
    _has_table_shape,
    _is_table_sequence,
    _looks_like_markdown_table,
    _looks_like_table_entry,
    _make_table_fallback_id,
    _normalize_bbox,
    _normalize_id_list,
    _normalize_int,
    _normalize_markdown_table,
    _normalize_ref_id,
    _normalize_str,
    _pick_first,
)
from modules.assembly.ir import AssemblyResult, AssemblyWarning, AssembledDocument, TableRef
from modules.assembly.types import AssemblySourceType


def from_table_output(raw: Any) -> AssemblyResult:
    """검증된 table 추출 payload 형태를 adapter_seed 결과로 바꾼다."""
    if isinstance(raw, AssemblyResult):
        return raw
    if raw is None:
        return AssemblyResult(
            metadata=_build_adapter_metadata(
                stage="adapter_seed",
                adapter="table",
                source="empty",
            ),
            raw=raw,
        )

    table_refs, warnings = _extract_table_refs(raw)
    return AssemblyResult(
        document=AssembledDocument(
            table_refs=table_refs,
            metadata=_extract_table_document_metadata(raw),
            raw=raw,
        ),
        warnings=warnings,
        metadata=_build_adapter_metadata(
            stage="adapter_seed",
            adapter="table",
            source=_infer_table_source(raw),
            table_count=len(table_refs),
        ),
        raw=raw,
    )


def _resolve_table_source(raw: Any) -> Any:
    if isinstance(raw, dict):
        nested = _pick_first(raw, TABLE_CONTAINER_KEYS)
        if nested is not None:
            return nested

    if _has_table_shape(raw) and not _has_layout_shape(raw):
        return raw
    return None


def _infer_table_source(raw: Any) -> AssemblySourceType:
    if raw is None:
        return "empty"
    if _is_table_sequence(raw):
        return "direct_list"
    if isinstance(raw, dict):
        if _pick_first(raw, TABLE_CONTAINER_KEYS) is not None:
            return "table_container"
        return "raw"
    return "raw"


def _extract_table_document_metadata(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    return _extract_metadata(raw, {*TABLE_LIST_KEYS, *TABLE_MARKDOWN_KEYS})


def _extract_table_refs(raw: Any) -> tuple[list[TableRef], list[AssemblyWarning]]:
    table_refs: list[TableRef] = []
    warnings: list[AssemblyWarning] = []

    for index, item in enumerate(_extract_table_entries(raw), start=1):
        table_ref, item_warnings = _build_table_ref(
            item,
            fallback_page=None,
            fallback_id=_make_table_fallback_id(index),
        )
        if table_ref is not None:
            table_refs.append(table_ref)
        warnings.extend(item_warnings)

    return table_refs, warnings


def _extract_table_entries(raw: Any) -> list[Any]:
    """table container와 markdown 문자열을 table entry payload로 펼친다."""
    if raw is None:
        return []
    if _looks_like_markdown_table(raw):
        return [{"markdown": raw}]

    if isinstance(raw, list):
        return [
            {"markdown": item} if _looks_like_markdown_table(item) else item
            for item in raw
        ]
    if not isinstance(raw, dict):
        return [raw]

    table_entries = _coerce_list(_pick_first(raw, TABLE_LIST_KEYS))
    if table_entries:
        return [
            {"markdown": item} if _looks_like_markdown_table(item) else item
            for item in table_entries
        ]
    if _looks_like_table_entry(raw):
        return [raw]
    return []


def _build_table_ref(
    raw: Any,
    fallback_page: int | None,
    fallback_id: str,
) -> tuple[TableRef | None, list[AssemblyWarning]]:
    """table entry 하나를 정규화하면서 markdown과 source metadata를 보존한다."""
    warnings: list[AssemblyWarning] = []
    if isinstance(raw, TableRef):
        return raw, warnings

    payload = _coerce_table_payload(raw)
    metadata = _extract_metadata(
        payload,
        {
            *TABLE_ID_KEYS,
            *PAGE_NUMBER_KEYS,
            *BBOX_KEYS,
            *CAPTION_KEYS,
            *NOTE_KEYS,
            *SOURCE_BLOCK_IDS_KEYS,
        },
    )

    markdown = _normalize_markdown_table(_pick_first(payload, TABLE_MARKDOWN_KEYS))
    if markdown is not None:
        metadata["markdown"] = markdown
        metadata["content_format"] = "markdown"

    table_id, generated_table_id, id_warnings = _resolve_table_id(
        payload,
        fallback_id,
        fallback_page,
        raw,
    )
    if generated_table_id:
        metadata["generated_table_id"] = True
    warnings.extend(id_warnings)
    page, generated_page, page_warnings = _resolve_table_page(
        payload,
        fallback_page,
        table_id,
        raw,
    )
    if generated_page:
        metadata["generated_page"] = True
    warnings.extend(page_warnings)

    return (
        TableRef(
            table_id=table_id,
            page=page,
            bbox=_normalize_bbox(_pick_first(payload, BBOX_KEYS) or payload),
            caption_id=_normalize_ref_id(_pick_first(payload, CAPTION_KEYS)),
            note_ids=_normalize_id_list(_pick_first(payload, NOTE_KEYS)),
            source_block_ids=_extract_source_block_ids(payload),
            metadata=metadata,
            raw=raw,
        ),
        warnings,
    )


def _coerce_table_payload(raw: Any) -> dict[str, Any]:
    if _looks_like_markdown_table(raw):
        return {"markdown": raw}
    if isinstance(raw, dict):
        return raw
    return {"table_id": raw}


def _resolve_table_id(
    payload: dict[str, Any],
    fallback_id: str,
    fallback_page: int | None,
    raw: Any,
) -> tuple[str, bool, list[AssemblyWarning]]:
    table_id = _normalize_str(_pick_first(payload, TABLE_ID_KEYS))
    if table_id is not None:
        return table_id, False, []

    return (
        fallback_id,
        True,
        [
            AssemblyWarning(
                code=WARNING_TABLE_MISSING_ID,
                message="table result is missing table_id; generated a fallback id.",
                level="info",
                page=fallback_page,
                element_ids=[fallback_id],
                raw=raw,
            )
        ],
    )


def _resolve_table_page(
    payload: dict[str, Any],
    fallback_page: int | None,
    table_id: str,
    raw: Any,
) -> tuple[int, bool, list[AssemblyWarning]]:
    page = _normalize_int(_pick_first(payload, PAGE_NUMBER_KEYS), default=fallback_page)
    if page is not None:
        return page, False, []

    page = 1
    return (
        page,
        True,
        [
            AssemblyWarning(
                code=WARNING_TABLE_MISSING_PAGE,
                message="table result is missing page information; defaulted to page 1.",
                level="warning",
                page=page,
                element_ids=[table_id],
                raw=raw,
            )
        ],
    )
