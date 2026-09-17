from __future__ import annotations

from collections.abc import Iterator
from urllib.parse import urljoin

import httpx

from .models import Attachment, HierarchyNode, Page


class ConfluenceError(RuntimeError):
    pass


class ConfluenceClient:
    """Small read-only client for the Confluence Cloud REST API v2."""

    def __init__(
        self,
        base_url: str,
        email: str,
        api_token: str,
        *,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_root = f"{self.base_url}/wiki/api/v2"
        self.http = httpx.Client(
            auth=(email, api_token),
            headers={"Accept": "application/json", "User-Agent": "confluence2obsidian/0.3"},
            timeout=timeout,
            follow_redirects=True,
        )

    def close(self) -> None:
        self.http.close()

    def __enter__(self) -> "ConfluenceClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _get_json(self, path_or_url: str, params: dict | None = None) -> dict:
        url = path_or_url if path_or_url.startswith("http") else f"{self.api_root}{path_or_url}"
        response = self.http.get(url, params=params)
        if response.status_code >= 400:
            detail = response.text[:1000]
            raise ConfluenceError(f"Confluence returned HTTP {response.status_code} for {url}: {detail}")
        return response.json()

    def _paginate(self, path: str, params: dict | None = None) -> Iterator[dict]:
        url: str | None = f"{self.api_root}{path}"
        first = True
        while url:
            data = self._get_json(url, params=params if first else None)
            first = False
            for item in data.get("results") or []:
                yield item
            next_link = (data.get("_links") or {}).get("next")
            url = urljoin(self.base_url, next_link) if next_link else None

    def list_spaces(self) -> list[dict]:
        return list(self._paginate("/spaces", {"limit": 250, "status": "current"}))

    def get_space_by_key(self, key: str) -> dict:
        matches = list(self._paginate("/spaces", {"keys": key, "limit": 25, "status": "current"}))
        for space in matches:
            if str(space.get("key", "")).lower() == key.lower():
                return space
        raise ConfluenceError(f"No accessible Confluence space with key {key!r}")

    def get_page(self, page_id: str, *, include_labels: bool = True) -> Page:
        data = self._get_json(
            f"/pages/{page_id}",
            {
                "body-format": "storage",
                "include-version": "true",
                "include-labels": str(include_labels).lower(),
            },
        )
        return Page.from_api(data)

    def get_pages_in_space(self, space_id: str) -> list[Page]:
        raw = list(
            self._paginate(
                f"/spaces/{space_id}/pages",
                {"limit": 250, "depth": "all", "status": "current"},
            )
        )
        return [self.get_page(str(item["id"])) for item in raw]

    def get_page_ancestors(self, page_id: str) -> list[dict]:
        """Return Confluence content-tree ancestors from top to bottom."""
        return list(self._paginate(f"/pages/{page_id}/ancestors", {"limit": 250}))

    def get_hierarchy_node(self, node_type: str, node_id: str) -> HierarchyNode:
        """Fetch title/parent metadata for a content-tree node used as a path component."""
        node_type = node_type.lower().rstrip("s")
        endpoint = {
            "page": "pages",
            "folder": "folders",
            "whiteboard": "whiteboards",
            "database": "databases",
            "embed": "embeds",
        }.get(node_type)
        if endpoint is None:
            return HierarchyNode(id=str(node_id), type=node_type, title=f"{node_type.title()} {node_id}")
        data = self._get_json(f"/{endpoint}/{node_id}")
        return HierarchyNode.from_api(data, fallback_type=node_type)

    def build_hierarchy(self, pages: list[Page]) -> dict[str, HierarchyNode]:
        """
        Build enough of Confluence's mixed content tree to place every exported page.

        Page listings alone are insufficient because a page may live below a real
        Confluence folder, database, whiteboard, or embed. We only fetch ancestor
        metadata for pages whose parent is missing from the page list, and cache it.
        """
        nodes: dict[str, HierarchyNode] = {p.id: HierarchyNode.from_page(p) for p in pages}

        for page in pages:
            if not page.parent_id or page.parent_id in nodes:
                continue
            ancestors = self.get_page_ancestors(page.id)
            for ancestor in ancestors:
                ancestor_id = str(ancestor.get("id") or "")
                if not ancestor_id or ancestor_id in nodes:
                    continue
                ancestor_type = str(ancestor.get("type") or "page").lower()
                try:
                    nodes[ancestor_id] = self.get_hierarchy_node(ancestor_type, ancestor_id)
                except ConfluenceError:
                    # Preserve the chain even if a non-page ancestor's details are not readable.
                    nodes[ancestor_id] = HierarchyNode(
                        id=ancestor_id,
                        type=ancestor_type,
                        title=str(ancestor.get("title") or f"{ancestor_type.title()} {ancestor_id}"),
                    )
        return nodes

    def get_attachments(self, page_id: str) -> list[Attachment]:
        raw = self._paginate(f"/pages/{page_id}/attachments", {"limit": 250, "status": "current"})
        out: list[Attachment] = []
        for item in raw:
            try:
                out.append(Attachment.from_api(item))
            except ValueError:
                continue
        return out

    def download_attachment(self, page_id: str, attachment: Attachment) -> bytes:
        # Use the authenticated REST download endpoint. Browser-style downloadLink
        # values returned in attachment metadata can 404 for API-token clients.
        url = (
            f"{self.base_url}/wiki/rest/api/content/{page_id}"
            f"/child/attachment/{attachment.id}/download"
        )
        response = self.http.get(url, headers={"Accept": "*/*"})
        if response.status_code >= 400:
            raise ConfluenceError(
                f"Could not download attachment {attachment.title!r} "
                f"(page {page_id}, attachment {attachment.id}): HTTP {response.status_code}"
            )
        return response.content
