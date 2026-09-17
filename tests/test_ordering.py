from pathlib import Path

import yaml

from confluence2obsidian.models import HierarchyNode, Page
from confluence2obsidian.vault import VaultExporter


def p(pid, title, parent=None, parent_type="page", position=None):
    return Page(
        id=str(pid),
        title=title,
        space_id="1",
        parent_id=str(parent) if parent else None,
        parent_type=parent_type if parent else None,
        position=position,
        version=1,
        body_storage="",
    )


def test_page_and_hierarchy_parse_position():
    data = {
        "id": "42",
        "title": "A page",
        "spaceId": "1",
        "parentId": "10",
        "parentType": "folder",
        "position": 238,
        "version": {"number": 3},
        "body": {"storage": {"value": ""}},
    }
    page = Page.from_api(data)
    node = HierarchyNode.from_api({**data, "type": "page"})
    assert page.position == 238
    assert node.position == 238


def test_sorting_spec_preserves_mixed_sibling_order():
    exporter = object.__new__(VaultExporter)
    pages = [
        p(1, "Thoughts", 100, "folder", 10),
        p(2, "Wet Lab Plan", 100, "folder", 20),
        p(3, "Delete all but extracellular residues chimerax", 100, "folder", 30),
        p(4, "Nanobody", 200, "folder", 5),
        p(5, "Introduction", 300, "folder", 5),
        p(6, "Notes Medchemcases Prof Gmeiner", 100, "folder", 60),
        p(7, "Notes Hossein Batebi", 100, "folder", 70),
        p(8, "Structures", 100, "folder", 80),
        p(9, "Notes SFB1423 Prof Heitman", 1, "page", 1),
    ]
    hierarchy = {
        "100": HierarchyNode(id="100", type="folder", title="GPCR Immunisation", position=1),
        "200": HierarchyNode(id="200", type="folder", title="Comp Methods", parent_id="100", parent_type="folder", position=40),
        "300": HierarchyNode(id="300", type="folder", title="Writing", parent_id="100", parent_type="folder", position=50),
    }
    hierarchy.update({page.id: HierarchyNode.from_page(page) for page in pages})

    spec = str(exporter._sorting_spec(hierarchy, "My Space"))
    block = spec.split("target-folder: My Space/GPCR Immunisation\n", 1)[1].split("\ntarget-folder:", 1)[0]
    expected_order = [
        "Thoughts",
        "Wet Lab Plan",
        "Delete all but extracellular residues chimerax",
        "Comp Methods",
        "Writing",
        "Notes Medchemcases Prof Gmeiner",
        "Notes Hossein Batebi",
        "Structures",
    ]
    indexes = [block.index(name) for name in expected_order]
    assert indexes == sorted(indexes)


def test_sorting_spec_targets_page_folder_note_children():
    exporter = object.__new__(VaultExporter)
    pages = [p(1, "Thoughts", 100, "folder", 10), p(9, "Child", 1, "page", 1)]
    hierarchy = {
        "100": HierarchyNode(id="100", type="folder", title="GPCR Immunisation", position=1),
        **{page.id: HierarchyNode.from_page(page) for page in pages},
    }
    spec = str(exporter._sorting_spec(hierarchy, "My Space"))
    assert "target-folder: My Space/GPCR Immunisation/Thoughts" in spec
    assert "Child" in spec
    assert "{:%parent-folder-name%:}" in spec


class FakeClient:
    base_url = "https://example.atlassian.net"

    def get_attachments(self, page_id):
        return []


def test_space_folder_note_contains_valid_literal_sorting_spec(tmp_path):
    exporter = VaultExporter(tmp_path, FakeClient())
    space = {"id": "1", "key": "LAB", "name": "Lab"}
    rel = exporter._write_space_folder_note(
        space,
        "Lab",
        exporter._sorting_spec(
            {"10": HierarchyNode(id="10", type="folder", title="Methods", position=1)},
            "Lab",
        ),
    )
    assert rel == Path("Lab/Lab.md")
    text = (tmp_path / rel).read_text()
    frontmatter = text.split("---", 2)[1]
    parsed = yaml.safe_load(frontmatter)
    assert parsed["confluence_type"] == "space"
    assert "target-folder: Lab" in parsed["sorting-spec"]
    assert "Methods" in parsed["sorting-spec"]
