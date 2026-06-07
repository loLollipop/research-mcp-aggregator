"""Tests for the writing adapter (no network needed)."""

import pytest

from research_mcp.adapters.writing_adapter import WritingAdapter


@pytest.fixture
def adapter():
    return WritingAdapter()


@pytest.mark.asyncio
async def test_format_bibtex(adapter):
    result = await adapter.format_bibtex(
        title="Deep Learning",
        authors=["Yann LeCun", "Yoshua Bengio", "Geoffrey Hinton"],
        year=2015,
        journal="Nature",
        doi="10.1038/nature14539",
    )
    assert result["key"] == "LeCun2015"
    assert "@article{LeCun2015," in result["bibtex"]
    assert "Yann LeCun and Yoshua Bengio and Geoffrey Hinton" in result["bibtex"]
    assert "doi       = {10.1038/nature14539}" in result["bibtex"]


@pytest.mark.asyncio
async def test_format_bibtex_custom_key(adapter):
    result = await adapter.format_bibtex(
        title="Attention Is All You Need",
        authors=["Ashish Vaswani"],
        year=2017,
        key="vaswani2017attention",
    )
    assert result["key"] == "vaswani2017attention"


@pytest.mark.asyncio
async def test_generate_citation_key(adapter):
    result = await adapter.generate_citation_key("Smith", 2024)
    assert result["key"] == "Smith2024"


@pytest.mark.asyncio
async def test_generate_citation_key_with_title(adapter):
    result = await adapter.generate_citation_key("Zhang", 2023, title="Transformer Networks")
    assert result["key"] == "Zhang2023Tran"


@pytest.mark.asyncio
async def test_format_bibtex_escapes_fields_and_normalizes_key(adapter):
    result = await adapter.format_bibtex(
        title="A {Hard} Paper\nWith Breaks",
        authors=["Ada {Lovelace}"],
        year=1843,
        abstract="Uses \\symbols and {braces}",
        key="Ada Lovelace 1843!",
    )

    assert result["key"] == "AdaLovelace1843"
    assert "@misc{AdaLovelace1843," in result["bibtex"]
    assert r"title     = {A \{Hard\} Paper With Breaks}" in result["bibtex"]
    assert r"author    = {Ada \{Lovelace\}}" in result["bibtex"]
    assert r"abstract  = {Uses \\symbols and \{braces\}}" in result["bibtex"]


@pytest.mark.asyncio
async def test_generate_citation_key_normalizes_generated_key(adapter):
    result = await adapter.generate_citation_key("D'Arcy", 2024, title="Graph Neural Networks")

    assert result["key"] == "DArcy2024Grap"


@pytest.mark.asyncio
async def test_parse_bibtex(adapter):
    bibtex = """@article{lecun2015deep,
  title     = {Deep learning},
  author    = {Yann LeCun and Yoshua Bengio and Geoffrey Hinton},
  year      = {2015},
  journal   = {Nature},
  doi       = {10.1038/nature14539}
}"""
    result = await adapter.parse_bibtex(bibtex)
    assert result["type"] == "article"
    assert result["key"] == "lecun2015deep"
    assert result["title"] == "Deep learning"
    assert len(result["authors"]) == 3
    assert result["year"] == 2015
