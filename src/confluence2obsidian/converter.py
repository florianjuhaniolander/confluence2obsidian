from __future__ import annotations

import html
import re
from collections.abc import Mapping

from bs4 import BeautifulSoup, NavigableString, Tag
from markdownify import markdownify as md


_CODE_LANG_RE = re.compile(r"^[A-Za-z0-9_+.#-]+$")


def _plain_text(tag: Tag | None) -> str:
    return tag.get_text(" ", strip=True) if tag else ""


def _macro_param(macro: Tag, name: str) -> str | None:
    for p in macro.find_all(lambda t: isinstance(t, Tag) and t.name == "ac:parameter"):
        if p.get("ac:name") == name or p.get("name") == name:
            return p.get_text(" ", strip=True)
    return None


def _macro_body(macro: Tag) -> str:
    body = macro.find(
        lambda t: isinstance(t, Tag)
        and t.name in {"ac:rich-text-body", "ac:plain-text-body"}
    )
    return body.decode_contents() if body else ""


def _callout(kind: str, title: str | None, markdown_body: str) -> str:
    header = f"> [!{kind}]" + (f" {title}" if title else "")
    body_lines = markdown_body.strip().splitlines() or [""]
    return "\n".join([header, *[("> " + line) if line else ">" for line in body_lines]]) + "\n"


def _replace_macros(soup: BeautifulSoup) -> None:
    macros = list(soup.find_all(lambda t: isinstance(t, Tag) and t.name == "ac:structured-macro"))
    for macro in macros:
        name = (macro.get("ac:name") or macro.get("name") or "unknown").lower()
        body_html = _macro_body(macro)
        body_markdown = md(body_html, heading_style="ATX", bullets="-").strip()
        title = _macro_param(macro, "title")

        if name in {"info", "note", "warning", "tip"}:
            replacement = _callout(name, title, body_markdown)
        elif name in {"panel"}:
            replacement = _callout("note", title, body_markdown)
        elif name in {"expand", "details"}:
            summary = html.escape(title or "Details")
            replacement = f"<details>\n<summary>{summary}</summary>\n\n{body_markdown}\n\n</details>\n"
        elif name == "code":
            lang = _macro_param(macro, "language") or ""
            lang = lang if _CODE_LANG_RE.match(lang) else ""
            raw = BeautifulSoup(body_html, "html.parser").get_text()
            replacement = f"```{lang}\n{raw.rstrip()}\n```\n"
        elif name in {"toc", "table-of-contents"}:
            replacement = "<!-- Confluence TOC omitted; Obsidian can generate a TOC if desired. -->\n"
        elif name in {"children", "children-display"}:
            replacement = "<!-- Confluence children macro: page hierarchy is preserved by the exporter. -->\n"
        else:
            escaped = html.escape(name)
            payload = body_markdown or "(no textual body)"
            replacement = _callout(
                "warning",
                f"Unsupported Confluence macro: {escaped}",
                payload,
            )
        macro.replace_with(NavigableString("\n" + replacement + "\n"))


def _replace_images(soup: BeautifulSoup) -> None:
    for image in list(soup.find_all(lambda t: isinstance(t, Tag) and t.name == "ac:image")):
        attachment = image.find(lambda t: isinstance(t, Tag) and t.name == "ri:attachment")
        if attachment:
            filename = attachment.get("ri:filename") or attachment.get("filename")
            if filename:
                image.replace_with(NavigableString(f"![[{filename}]]"))
                continue
        url_tag = image.find(lambda t: isinstance(t, Tag) and t.name == "ri:url")
        if url_tag:
            url = url_tag.get("ri:value") or url_tag.get("value")
            if url:
                image.replace_with(NavigableString(f"![]({url})"))


def _replace_attachment_links(soup: BeautifulSoup) -> None:
    for link in list(soup.find_all("a")):
        attachment = link.find(lambda t: isinstance(t, Tag) and t.name == "ri:attachment")
        if attachment:
            filename = attachment.get("ri:filename") or attachment.get("filename")
            if filename:
                label = link.get_text(" ", strip=True)
                wiki = f"[[{filename}|{label}]]" if label and label != filename else f"[[{filename}]]"
                link.replace_with(NavigableString(wiki))


def _replace_page_links(soup: BeautifulSoup, title_to_link: Mapping[str, str]) -> None:
    # Confluence storage format commonly embeds <ri:page ...> inside <ac:link>.
    for ac_link in list(soup.find_all(lambda t: isinstance(t, Tag) and t.name == "ac:link")):
        page = ac_link.find(lambda t: isinstance(t, Tag) and t.name == "ri:page")
        if not page:
            continue
        title = page.get("ri:content-title") or page.get("content-title")
        if not title:
            continue
        label_tag = ac_link.find(
            lambda t: isinstance(t, Tag) and t.name in {"ac:plain-text-link-body", "ac:link-body"}
        )
        label = _plain_text(label_tag) or title
        target = title_to_link.get(title, title)
        wiki = f"[[{target}|{label}]]" if label != title or target != title else f"[[{target}]]"
        ac_link.replace_with(NavigableString(wiki))


def _normalize_markdown(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text.strip() + "\n"


def storage_to_markdown(storage: str, title_to_link: Mapping[str, str] | None = None) -> str:
    """Convert Confluence storage XHTML/XML-ish markup into Obsidian-friendly Markdown."""
    title_to_link = title_to_link or {}
    soup = BeautifulSoup(storage or "", "html.parser")
    _replace_macros(soup)
    _replace_images(soup)
    _replace_attachment_links(soup)
    _replace_page_links(soup, title_to_link)
    text = md(str(soup), heading_style="ATX", bullets="-")
    return _normalize_markdown(text)
