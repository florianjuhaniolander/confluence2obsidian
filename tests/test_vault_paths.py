from pathlib import Path

from confluence2obsidian.models import HierarchyNode, Page
from confluence2obsidian.vault import VaultExporter


def p(pid, title, parent=None, parent_type="page"):
    return Page(
        id=str(pid), title=title, space_id="1", parent_id=str(parent) if parent else None,
        parent_type=parent_type if parent else None, version=1, body_storage=""
    )


def test_hierarchy_paths_use_folder_notes():
    exporter = object.__new__(VaultExporter)
    pages = [p(1, "Root"), p(2, "Child", 1), p(3, "Grandchild", 2)]
    hierarchy = {page.id: HierarchyNode.from_page(page) for page in pages}
    paths = exporter._paths_for_pages(pages, "Lab", hierarchy)
    assert paths["1"] == Path("Lab/Root/Root.md")
    assert paths["2"] == Path("Lab/Root/Child/Child.md")
    assert paths["3"] == Path("Lab/Root/Child/Grandchild.md")


def test_real_confluence_folder_is_preserved():
    exporter = object.__new__(VaultExporter)
    pages = [p(2, "Protocol", 10, "folder")]
    hierarchy = {
        "10": HierarchyNode(id="10", type="folder", title="Methods"),
        "2": HierarchyNode.from_page(pages[0]),
    }
    paths = exporter._paths_for_pages(pages, "Lab", hierarchy)
    assert paths["2"] == Path("Lab/Methods/Protocol.md")


def test_page_below_folder_and_parent_page():
    exporter = object.__new__(VaultExporter)
    pages = [p(1, "Protein Design", 10, "folder"), p(2, "GPCR", 1)]
    hierarchy = {
        "10": HierarchyNode(id="10", type="folder", title="Projects"),
        "1": HierarchyNode.from_page(pages[0]),
        "2": HierarchyNode.from_page(pages[1]),
    }
    paths = exporter._paths_for_pages(pages, "Lab", hierarchy)
    assert paths["1"] == Path("Lab/Projects/Protein Design/Protein Design.md")
    assert paths["2"] == Path("Lab/Projects/Protein Design/GPCR.md")
