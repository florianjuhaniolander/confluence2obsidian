from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import yaml

from .confluence import ConfluenceClient
from .converter import storage_to_markdown
from .models import ExportedPage, HierarchyNode, Page
from .util import ensure_within, safe_name


STATE_DIR = ".confluence-sync"
STATE_FILE = "state.json"
STATE_FORMAT_VERSION = 3


class _LiteralString(str):
    """Marker used to make multiline YAML frontmatter readable."""


class _FrontmatterDumper(yaml.SafeDumper):
    pass


def _represent_literal(dumper: yaml.SafeDumper, data: _LiteralString):
    return dumper.represent_scalar("tag:yaml.org,2002:str", str(data), style="|")


_FrontmatterDumper.add_representer(_LiteralString, _represent_literal)


def _dump_frontmatter(data: dict) -> str:
    return yaml.dump(
        data,
        Dumper=_FrontmatterDumper,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    ).strip()


class VaultExporter:
    def __init__(self, vault: Path, client: ConfluenceClient) -> None:
        self.vault = vault.expanduser().resolve()
        self.client = client
        self.state_path = self.vault / STATE_DIR / STATE_FILE
        self.state = self._load_state()

    def _load_state(self) -> dict:
        if not self.state_path.exists():
            return {"pages": {}, "format_version": STATE_FORMAT_VERSION}
        try:
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"pages": {}, "format_version": STATE_FORMAT_VERSION}

    def _save_state(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state["format_version"] = STATE_FORMAT_VERSION
        self.state["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.state_path.write_text(json.dumps(self.state, indent=2, sort_keys=True), encoding="utf-8")

    @staticmethod
    def _children_by_parent(nodes: dict[str, HierarchyNode]) -> dict[str, list[str]]:
        children: dict[str, list[str]] = {}
        for node in nodes.values():
            if node.parent_id:
                children.setdefault(node.parent_id, []).append(node.id)
        return children

    @staticmethod
    def _sort_key(node: HierarchyNode) -> tuple:
        # Confluence's position is the authoritative sibling order. Keep a
        # deterministic fallback for rare/malformed nodes without a position.
        return (
            node.position is None,
            node.position if node.position is not None else 0,
            node.title.casefold(),
            node.id,
        )

    def _container_paths(
        self,
        hierarchy: dict[str, HierarchyNode],
        space_folder: str,
    ) -> dict[str, Path]:
        """Return the filesystem directory that represents each tree node."""
        memo: dict[str, Path] = {}
        visiting: set[str] = set()

        def resolve(node_id: str) -> Path:
            if node_id in memo:
                return memo[node_id]
            node = hierarchy.get(node_id)
            if node is None:
                return Path(space_folder)
            if node_id in visiting:
                return Path(space_folder)
            visiting.add(node_id)
            if node.parent_id and node.parent_id in hierarchy:
                base = resolve(node.parent_id)
            else:
                base = Path(space_folder)
            out = base / safe_name(node.title, fallback=f"{node.type}-{node.id}")
            visiting.discard(node_id)
            memo[node_id] = out
            return out

        for node_id in hierarchy:
            resolve(node_id)
        return memo

    def _paths_for_pages(
        self,
        pages: list[Page],
        space_folder: str,
        hierarchy: dict[str, HierarchyNode] | None = None,
    ) -> dict[str, Path]:
        """
        Mirror the Confluence content tree using folder notes.

        Confluence pages can both contain content and have children; a filesystem
        path cannot simultaneously be `Parent.md` and a `Parent/` directory. For
        pages with children we therefore write `Parent/Parent.md`, and place the
        children in the same `Parent/` directory. Real Confluence folders become
        ordinary directories without a synthetic content note.
        """
        hierarchy = hierarchy or {p.id: HierarchyNode.from_page(p) for p in pages}
        page_by_id = {p.id: p for p in pages}
        children = self._children_by_parent(hierarchy)
        containers = self._container_paths(hierarchy, space_folder)

        paths: dict[str, Path] = {}
        for page in pages:
            node = hierarchy.get(page.id) or HierarchyNode.from_page(page)
            if node.parent_id and node.parent_id in hierarchy:
                parent_dir = containers[node.parent_id]
            else:
                parent_dir = Path(space_folder)

            filename = safe_name(page.title) + ".md"
            if children.get(page.id):
                # Folder-note layout: Parent/Parent.md
                rel = containers[page.id] / filename
            else:
                rel = parent_dir / filename
            paths[page.id] = rel

        # Resolve file collisions deterministically by adding the Confluence id.
        seen: dict[str, str] = {}
        for page_id, rel in list(paths.items()):
            key = str(rel).casefold()
            if key in seen and seen[key] != page_id:
                page = page_by_id[page_id]
                paths[page_id] = rel.with_name(f"{safe_name(page.title)} [{page.id}].md")
            else:
                seen[key] = page_id
        return paths

    def _sorting_spec(
        self,
        hierarchy: dict[str, HierarchyNode],
        space_folder: str,
    ) -> _LiteralString:
        """
        Build an obsidian-custom-sort specification mirroring Confluence order.

        Explicit names are used instead of filename prefixes. This keeps note
        names clean and preserves the intermixing of pages and real folders.
        """
        containers = self._container_paths(hierarchy, space_folder)
        children: dict[str | None, list[HierarchyNode]] = {}

        for node in hierarchy.values():
            if node.parent_id and node.parent_id in hierarchy:
                parent_key: str | None = node.parent_id
            else:
                parent_key = None
            children.setdefault(parent_key, []).append(node)

        sections: list[str] = []
        for parent_id, siblings in children.items():
            if not siblings:
                continue
            target = Path(space_folder) if parent_id is None else containers[parent_id]
            ordered = sorted(siblings, key=self._sort_key)
            sections.append(f"target-folder: {target.as_posix()}")
            # If this directory is represented by a folder note, keep that note
            # at the top when it is visible. Folder-note plugins normally hide it.
            sections.append("{:%parent-folder-name%:}")
            sections.extend(safe_name(node.title, fallback=f"{node.type}-{node.id}") for node in ordered)
            # Keep local-only notes/attachment folders rather than suppressing them.
            sections.append("%")
            sections.append("")

        return _LiteralString("\n".join(sections).rstrip() + "\n")

    @staticmethod
    def _title_links(pages: list[Page], paths: dict[str, Path]) -> dict[str, str]:
        counts: dict[str, int] = {}
        for p in pages:
            counts[p.title] = counts.get(p.title, 0) + 1
        out: dict[str, str] = {}
        for p in pages:
            if counts[p.title] == 1:
                out[p.title] = paths[p.id].with_suffix("").as_posix()
        return out

    def _write_space_folder_note(
        self,
        space: dict,
        space_folder: str,
        sorting_spec: _LiteralString,
    ) -> Path:
        """Create the hidden-by-folder-note-plugin note carrying sort rules."""
        rel = Path(space_folder) / f"{space_folder}.md"
        destination = ensure_within(self.vault, self.vault / rel)
        destination.parent.mkdir(parents=True, exist_ok=True)
        frontmatter = {
            "confluence_type": "space",
            "confluence_space_id": str(space.get("id") or ""),
            "confluence_space_key": str(space.get("key") or ""),
            "confluence_generated_container": True,
            "sorting-spec": sorting_spec,
            "synced_at": datetime.now(timezone.utc).isoformat(),
        }
        note = "---\n" + _dump_frontmatter(frontmatter) + "\n---\n\n"
        note += f"# {space.get('name') or space_folder}\n"
        destination.write_text(note, encoding="utf-8")
        self.state.setdefault("spaces", {})[str(space.get("id") or space_folder)] = {
            "path": rel.as_posix(),
            "name": str(space.get("name") or space_folder),
        }
        return rel

    def _cleanup_old_generated_path(self, old_rel: str | None, new_rel: Path) -> None:
        if not old_rel or old_rel == new_rel.as_posix():
            return
        old_path = ensure_within(self.vault, self.vault / Path(old_rel))
        if not old_path.exists() or not old_path.is_file():
            return
        old_path.unlink()
        parent = old_path.parent
        while parent != self.vault:
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent

    def export_page(
        self,
        page: Page,
        relative_path: Path,
        title_links: dict[str, str],
        *,
        force: bool = False,
        download_attachments: bool = True,
        extra_frontmatter: dict | None = None,
    ) -> ExportedPage:
        previous = (self.state.get("pages") or {}).get(page.id) or {}
        destination = ensure_within(self.vault, self.vault / relative_path)
        unchanged = (
            not force
            and destination.exists()
            and int(previous.get("version") or -1) == page.version
            and previous.get("path") == relative_path.as_posix()
            and previous.get("position") == page.position
            and int(previous.get("export_format") or 0) == STATE_FORMAT_VERSION
            and not extra_frontmatter
        )
        if unchanged:
            return ExportedPage(page=page, relative_path=relative_path, changed=False)

        destination.parent.mkdir(parents=True, exist_ok=True)
        body = storage_to_markdown(page.body_storage, title_links)
        source_url = urljoin(self.client.base_url, page.webui or "") if page.webui else self.client.base_url
        frontmatter = {
            "confluence_id": page.id,
            "confluence_type": "page",
            "confluence_space_id": page.space_id,
            "confluence_version": page.version,
            "confluence_position": page.position,
            "confluence_url": source_url,
            "confluence_parent_id": page.parent_id,
            "confluence_parent_type": page.parent_type,
            "tags": page.labels or None,
            "synced_at": datetime.now(timezone.utc).isoformat(),
        }
        if extra_frontmatter:
            frontmatter.update(extra_frontmatter)
        frontmatter = {k: v for k, v in frontmatter.items() if v is not None}
        note = "---\n" + _dump_frontmatter(frontmatter) + "\n---\n\n"
        note += f"# {page.title}\n\n{body}"
        destination.write_text(note, encoding="utf-8")

        attachment_records: dict[str, dict] = {}
        if download_attachments:
            attachments = self.client.get_attachments(page.id)
            if attachments:
                attachment_dir = destination.parent / "_attachments"
                attachment_dir.mkdir(parents=True, exist_ok=True)
                for att in attachments:
                    att_name = safe_name(att.title, fallback=f"attachment-{att.id}")
                    att_path = ensure_within(self.vault, attachment_dir / att_name)
                    old_att = (previous.get("attachments") or {}).get(att.id) or {}
                    if force or not att_path.exists() or int(old_att.get("version") or -1) != att.version:
                        att_path.write_bytes(self.client.download_attachment(page.id, att))
                    attachment_records[att.id] = {
                        "title": att.title,
                        "version": att.version,
                        "path": att_path.relative_to(self.vault).as_posix(),
                    }

        self._cleanup_old_generated_path(previous.get("path"), relative_path)
        self.state.setdefault("pages", {})[page.id] = {
            "title": page.title,
            "version": page.version,
            "position": page.position,
            "path": relative_path.as_posix(),
            "attachments": attachment_records,
            "export_format": STATE_FORMAT_VERSION,
        }
        return ExportedPage(page=page, relative_path=relative_path, changed=True)

    def export_space(
        self,
        space: dict,
        pages: list[Page],
        *,
        hierarchy: dict[str, HierarchyNode] | None = None,
        force: bool = False,
        download_attachments: bool = True,
    ) -> list[ExportedPage]:
        space_name = safe_name(str(space.get("name") or space.get("key") or space["id"]))
        hierarchy = hierarchy or {p.id: HierarchyNode.from_page(p) for p in pages}
        paths = self._paths_for_pages(pages, space_name, hierarchy)
        links = self._title_links(pages, paths)
        sorting_spec = self._sorting_spec(hierarchy, space_name)

        # The space folder note is where Custom File Explorer Sorting discovers
        # the generated sorting specification. If a real Confluence page already
        # occupies exactly that folder-note path, merge the spec into that page's
        # frontmatter instead of creating a synthetic note over it.
        space_note_rel = Path(space_name) / f"{space_name}.md"
        sort_owner_page_id = next(
            (page_id for page_id, rel in paths.items() if rel == space_note_rel),
            None,
        )
        extra_frontmatter: dict[str, dict] = {}
        if sort_owner_page_id is None:
            self._write_space_folder_note(space, space_name, sorting_spec)
        else:
            extra_frontmatter[sort_owner_page_id] = {"sorting-spec": sorting_spec}

        results = [
            self.export_page(
                page,
                paths[page.id],
                links,
                force=force,
                download_attachments=download_attachments,
                extra_frontmatter=extra_frontmatter.get(page.id),
            )
            for page in pages
        ]
        self._save_state()
        return results

    def export_single_page(
        self,
        page: Page,
        *,
        force: bool = False,
        download_attachments: bool = True,
    ) -> ExportedPage:
        rel = Path(safe_name(page.title) + ".md")
        result = self.export_page(
            page,
            rel,
            {page.title: rel.with_suffix("").as_posix()},
            force=force,
            download_attachments=download_attachments,
        )
        self._save_state()
        return result
