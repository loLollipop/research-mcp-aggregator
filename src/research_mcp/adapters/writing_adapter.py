"""Writing tools adapter - BibTeX, citation formatting, document helpers."""

from __future__ import annotations

import re
from typing import Any

from research_mcp.adapters import (
    AdapterMeta,
    BaseAdapter,
    ToolSpec,
    register_adapter,
)


@register_adapter
class WritingAdapter(BaseAdapter):
    """Research writing utilities: BibTeX formatting, citation key generation, etc."""

    def metadata(self) -> AdapterMeta:
        return AdapterMeta(
            name="writing",
            description="Research writing tools: BibTeX, citation keys, references",
            tools=[
                ToolSpec(
                    name="format_bibtex",
                    description="Format paper metadata into a BibTeX entry.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "title": {"type": "string", "description": "Paper title"},
                            "authors": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of author names",
                            },
                            "year": {"type": "integer", "description": "Publication year"},
                            "journal": {"type": "string", "description": "Journal or venue name"},
                            "doi": {"type": "string", "description": "DOI"},
                            "url": {"type": "string", "description": "Paper URL"},
                            "abstract": {"type": "string", "description": "Paper abstract"},
                            "key": {
                                "type": "string",
                                "description": "Custom citation key (auto-generated if empty)",
                            },
                        },
                        "required": ["title", "authors", "year"],
                    },
                    handler=self.format_bibtex,
                ),
                ToolSpec(
                    name="generate_citation_key",
                    description="Generate a citation key from author names and year.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "first_author": {
                                "type": "string",
                                "description": "First author last name",
                            },
                            "year": {"type": "integer", "description": "Publication year"},
                            "title": {
                                "type": "string",
                                "description": "Paper title (for disambiguation)",
                            },
                        },
                        "required": ["first_author", "year"],
                    },
                    handler=self.generate_citation_key,
                ),
                ToolSpec(
                    name="parse_bibtex",
                    description="Parse a BibTeX entry string and extract structured metadata.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "bibtex": {"type": "string", "description": "Raw BibTeX entry string"},
                        },
                        "required": ["bibtex"],
                    },
                    handler=self.parse_bibtex,
                ),
            ],
        )

    async def initialize(self, config: dict[str, Any] | None = None) -> None:
        pass

    async def format_bibtex(
        self,
        title: str,
        authors: list[str],
        year: int,
        journal: str = "",
        doi: str = "",
        url: str = "",
        abstract: str = "",
        key: str = "",
    ) -> dict[str, Any]:
        if not key and authors:
            first = authors[0].split()[-1]
            key = f"{first}{year}"
        elif not key:
            key = f"unknown{year}"

        bibtype = "article" if journal else "misc"
        author_str = " and ".join(authors)

        lines = [f"@{bibtype}{{{key},"]
        lines.append(f"  title     = {{{title}}},")
        lines.append(f"  author    = {{{author_str}}},")
        lines.append(f"  year      = {{{year}}},")
        if journal:
            lines.append(f"  journal   = {{{journal}}},")
        if doi:
            lines.append(f"  doi       = {{{doi}}},")
        if url:
            lines.append(f"  url       = {{{url}}},")
        if abstract:
            lines.append(f"  abstract  = {{{abstract}}},")
        lines.append("}")

        return {"key": key, "bibtex": "\n".join(lines)}

    async def generate_citation_key(
        self, first_author: str, year: int, title: str = ""
    ) -> dict[str, Any]:
        last = first_author.strip().split()[-1]
        key = f"{last}{year}"
        if title:
            words = [w for w in re.findall(r"[A-Za-z]+", title) if len(w) > 3]
            if words:
                key += words[0][:4].capitalize()
        return {"key": key}

    async def parse_bibtex(self, bibtex: str) -> dict[str, Any]:
        result: dict[str, Any] = {}
        # Extract type and key
        m = re.match(r"@(\w+)\s*\{\s*([^,\s]+)", bibtex)
        if m:
            result["type"] = m.group(1).lower()
            result["key"] = m.group(2)
        # Extract fields
        for field in [
            "title",
            "author",
            "year",
            "journal",
            "doi",
            "url",
            "abstract",
            "booktitle",
            "volume",
            "pages",
        ]:
            m = re.search(rf"{field}\s*=\s*\{{(.*?)\}}", bibtex, re.IGNORECASE | re.DOTALL)
            if m:
                result[field] = m.group(1).strip()
        # Parse authors
        if "author" in result:
            result["authors"] = [a.strip() for a in result["author"].split(" and ")]
        # Parse year as int
        if "year" in result:
            try:
                result["year"] = int(result["year"])
            except ValueError:
                pass
        return result
