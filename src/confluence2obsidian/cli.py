from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated

import typer

from . import __version__
from .confluence import ConfluenceClient, ConfluenceError
from .vault import VaultExporter

app = typer.Typer(
    no_args_is_help=True,
    help="Read-only Confluence Cloud → Obsidian exporter/sync tool.",
)


def _client() -> ConfluenceClient:
    missing = [
        name
        for name in ("CONFLUENCE_URL", "CONFLUENCE_EMAIL", "CONFLUENCE_API_TOKEN")
        if not os.getenv(name)
    ]
    if missing:
        raise typer.BadParameter(
            "Missing environment variable(s): " + ", ".join(missing) + ". See `confluence2obsidian init`."
        )
    return ConfluenceClient(
        os.environ["CONFLUENCE_URL"],
        os.environ["CONFLUENCE_EMAIL"],
        os.environ["CONFLUENCE_API_TOKEN"],
    )


@app.command()
def version() -> None:
    """Print the installed version."""
    typer.echo(__version__)


@app.command("init")
def init_command() -> None:
    """Show the minimal environment configuration (does not store credentials)."""
    typer.echo(
        "\n".join(
            [
                "Set these environment variables before running the exporter:",
                "",
                "  export CONFLUENCE_URL='https://YOUR-DOMAIN.atlassian.net'",
                "  export CONFLUENCE_EMAIL='you@example.com'",
                "  export CONFLUENCE_API_TOKEN='YOUR_API_TOKEN'",
                "",
                "Then test with:",
                "  confluence2obsidian spaces",
                "",
                "Credentials are never written into the vault or sync state.",
            ]
        )
    )


@app.command()
def spaces() -> None:
    """List accessible Confluence spaces."""
    try:
        with _client() as client:
            rows = client.list_spaces()
        for space in rows:
            typer.echo(f"{space.get('key', ''):12}  {space.get('id', ''):12}  {space.get('name', '')}")
    except ConfluenceError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)


@app.command()
def page(
    page_id: Annotated[str, typer.Argument(help="Confluence page ID")],
    vault: Annotated[Path, typer.Option("--vault", "-v", help="Target Obsidian vault directory")],
    force: Annotated[bool, typer.Option("--force", help="Rewrite even when version is unchanged")] = False,
    attachments: Annotated[
        bool, typer.Option("--attachments/--no-attachments", help="Download page attachments")
    ] = True,
) -> None:
    """Export or update one Confluence page."""
    try:
        with _client() as client:
            exporter = VaultExporter(vault, client)
            result = exporter.export_single_page(
                client.get_page(page_id), force=force, download_attachments=attachments
            )
        status = "updated" if result.changed else "unchanged"
        typer.echo(f"{status}: {result.relative_path}")
    except (ConfluenceError, OSError, ValueError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)


@app.command()
def sync(
    space: Annotated[str, typer.Option("--space", "-s", help="Confluence space key")],
    vault: Annotated[Path, typer.Option("--vault", "-v", help="Target Obsidian vault directory")],
    force: Annotated[bool, typer.Option("--force", help="Rewrite all pages")] = False,
    attachments: Annotated[
        bool, typer.Option("--attachments/--no-attachments", help="Download attachments")
    ] = True,
) -> None:
    """Export/sync all accessible current pages in a Confluence space."""
    try:
        vault.mkdir(parents=True, exist_ok=True)
        with _client() as client:
            space_obj = client.get_space_by_key(space)
            pages = client.get_pages_in_space(str(space_obj["id"]))
            hierarchy = client.build_hierarchy(pages)
            exporter = VaultExporter(vault, client)
            results = exporter.export_space(
                space_obj, pages, hierarchy=hierarchy, force=force, download_attachments=attachments
            )
        changed = sum(r.changed for r in results)
        typer.echo(f"Synced {len(results)} pages: {changed} updated, {len(results) - changed} unchanged")
    except (ConfluenceError, OSError, ValueError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
