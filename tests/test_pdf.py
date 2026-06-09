"""Tests for MinerU-backed PDF extraction tools."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any

import pytest

from research_mcp.adapters.pdf_adapter import MineruPDFError, PDFAdapter, html_table_to_text
from research_mcp.server import ResearchMCPServer


@pytest.mark.asyncio
async def test_pdf_check_config_masks_mineru_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MINERU_API_TOKEN", "secret-token")
    adapter = PDFAdapter()
    await adapter.initialize({})

    status = await adapter.check_config()

    assert status["api_token_configured"] is True
    assert status["api_token_env"] == "MINERU_API_TOKEN"
    assert "secret-token" not in json.dumps(status)


@pytest.mark.asyncio
async def test_pdf_extract_returns_structured_error_without_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("MINERU_API_TOKEN", raising=False)
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    adapter = PDFAdapter()
    await adapter.initialize({})

    result = await adapter.extract_mineru(str(pdf_path), output_dir=str(tmp_path / "mineru"))

    assert result["status"] == "error"
    assert result["error_type"] == "missing_api_token"
    assert "MINERU_API_TOKEN" in result["message"]


@pytest.mark.asyncio
async def test_pdf_extract_mineru_exports_pages_manifest_and_preview(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    adapter = PDFAdapter()
    await adapter.initialize({})

    async def fake_request_upload_batch(**_kwargs: Any) -> tuple[str, str]:
        return "batch-1", "https://upload.example/paper.pdf"

    async def fake_upload_file(*_args: Any, **_kwargs: Any) -> None:
        return None

    async def fake_poll_batch_result(**_kwargs: Any) -> dict[str, str]:
        return {"state": "done", "full_zip_url": "https://download.example/result.zip"}

    async def fake_download_file(_client: Any, _url: str, dest: Path) -> None:
        content_list = [
            {"type": "text", "text": "Title", "text_level": 1, "page_idx": 0},
            {"type": "text", "text": ["Intro", "paragraph"], "page_idx": 0},
            {
                "type": "table",
                "table_caption": ["Parameters"],
                "table_body": (
                    "<table><tr><th>A</th><th>B</th></tr>"
                    "<tr><td>1</td><td>2</td></tr></table>"
                ),
                "page_idx": 0,
            },
            {"type": "image", "image_caption": ["Figure 1 caption"], "page_idx": 1},
        ]
        with zipfile.ZipFile(dest, "w") as archive:
            archive.writestr("paper/full.md", "# Title\n\nIntro markdown\n")
            archive.writestr(
                "paper/paper_content_list.json",
                json.dumps(content_list),
            )

    monkeypatch.setattr(adapter, "_request_upload_batch", fake_request_upload_batch)
    monkeypatch.setattr(adapter, "_upload_file", fake_upload_file)
    monkeypatch.setattr(adapter, "_poll_batch_result", fake_poll_batch_result)
    monkeypatch.setattr(adapter, "_download_file", fake_download_file)

    result = await adapter.extract_mineru(
        str(pdf_path),
        output_dir=str(tmp_path / "mineru"),
        api_token="token",
        sync_workspace=False,
        preview_chars=100,
    )

    assert result["status"] == "ok"
    assert result["batch_id"] == "batch-1"
    assert result["page_count"] == 2
    assert result["heading_count"] == 1
    assert result["headings"] == [{"page": 1, "level": 1, "text": "Title"}]
    assert "Intro markdown" in result["text_preview"]

    pages_dir = Path(result["artifacts"]["pages_dir"])
    assert (pages_dir / "page_1.txt").read_text(encoding="utf-8").startswith("# Title")
    assert "A | B" in (pages_dir / "page_1.txt").read_text(encoding="utf-8")
    assert "[FIGURE CAPTION]" in (pages_dir / "page_2.txt").read_text(encoding="utf-8")
    assert Path(result["artifacts"]["manifest_file"]).exists()


def test_pdf_archive_extraction_rejects_path_traversal(tmp_path: Path) -> None:
    adapter = PDFAdapter()
    zip_path = tmp_path / "bad.zip"
    raw_dir = tmp_path / "raw"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("../evil.txt", "bad")

    with pytest.raises(MineruPDFError) as exc_info:
        adapter._extract_archive(zip_path, raw_dir)

    assert exc_info.value.error_type == "unsafe_archive"
    assert not (tmp_path / "evil.txt").exists()


def test_html_table_to_text_renders_mineru_table_body() -> None:
    table = "<table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table>"

    assert html_table_to_text(table) == "A | B\n1 | 2"


@pytest.mark.asyncio
async def test_server_registers_pdf_tools() -> None:
    server = ResearchMCPServer()
    await server.initialize({})
    try:
        assert "pdf_check_config" in server._tools
        assert "pdf_extract_mineru" in server._tools
    finally:
        await server.shutdown()
