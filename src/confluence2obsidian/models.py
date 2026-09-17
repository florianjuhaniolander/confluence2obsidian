from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class Page:
    id: str
    title: str
    space_id: str
    parent_id: str | None
    version: int
    body_storage: str
    parent_type: str | None = None
    position: int | None = None
    webui: str | None = None
    labels: list[str] = field(default_factory=list)

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "Page":
        body = data.get("body") or {}
        storage = body.get("storage") or {}
        version = data.get("version") or {}
        links = data.get("_links") or {}
        labels_raw = data.get("labels") or {}
        if isinstance(labels_raw, dict):
            labels_items = labels_raw.get("results") or []
        else:
            labels_items = labels_raw or []
        labels = [
            str(item.get("name"))
            for item in labels_items
            if isinstance(item, dict) and item.get("name")
        ]
        return cls(
            id=str(data["id"]),
            title=str(data.get("title") or f"Page {data['id']}"),
            space_id=str(data.get("spaceId") or ""),
            parent_id=str(data["parentId"]) if data.get("parentId") else None,
            parent_type=str(data.get("parentType")) if data.get("parentType") else None,
            position=int(data["position"]) if data.get("position") is not None else None,
            version=int(version.get("number") or 0),
            body_storage=str(storage.get("value") or ""),
            webui=links.get("webui"),
            labels=labels,
        )


@dataclass(slots=True)
class HierarchyNode:
    id: str
    type: str
    title: str
    parent_id: str | None = None
    parent_type: str | None = None
    position: int | None = None

    @classmethod
    def from_api(cls, data: dict[str, Any], *, fallback_type: str | None = None) -> "HierarchyNode":
        node_type = str(data.get("type") or fallback_type or "page").lower()
        return cls(
            id=str(data["id"]),
            type=node_type,
            title=str(data.get("title") or f"{node_type.title()} {data['id']}"),
            parent_id=str(data["parentId"]) if data.get("parentId") else None,
            parent_type=str(data.get("parentType")) if data.get("parentType") else None,
            position=int(data["position"]) if data.get("position") is not None else None,
        )

    @classmethod
    def from_page(cls, page: Page) -> "HierarchyNode":
        return cls(
            id=page.id,
            type="page",
            title=page.title,
            parent_id=page.parent_id,
            parent_type=page.parent_type,
            position=page.position,
        )


@dataclass(slots=True)
class Attachment:
    id: str
    title: str
    media_type: str | None
    download_link: str
    version: int

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "Attachment":
        links = data.get("_links") or {}
        version = data.get("version") or {}
        download = data.get("downloadLink") or links.get("download") or ""
        return cls(
            id=str(data["id"]),
            title=str(data.get("title") or data["id"]),
            media_type=data.get("mediaType"),
            download_link=str(download),
            version=int(version.get("number") or 0),
        )


@dataclass(slots=True)
class ExportedPage:
    page: Page
    relative_path: Path
    changed: bool
