"""Tests for the local docx adapter."""

import pytest

from research_mcp.adapters.docx_adapter import DocxAdapter


@pytest.mark.asyncio
async def test_docx_create_read_and_append(tmp_path):
    adapter = DocxAdapter()
    await adapter.initialize({})
    output = tmp_path / "report.docx"
    await adapter.create(str(output), title="Report", paragraphs=["Initial paragraph"])
    await adapter.add_heading(str(output), "Methods", level=1)
    await adapter.add_paragraph(str(output), "Second paragraph")
    await adapter.add_table(str(output), [["A", "B"], ["1", "2"]])

    result = await adapter.read(str(output))
    assert output.exists()
    assert "Report" in result["paragraphs"]
    assert "Initial paragraph" in result["paragraphs"]
    assert "Methods" in result["paragraphs"]
    assert result["tables"] == [[["A", "B"], ["1", "2"]]]
