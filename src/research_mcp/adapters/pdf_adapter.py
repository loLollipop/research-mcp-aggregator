"""PDF extraction adapter using MinerU cloud parsing."""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import time
import unicodedata
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import httpx

from research_mcp.adapters import AdapterMeta, BaseAdapter, ToolSpec, register_adapter

DEFAULT_MINERU_API_BASE = "https://mineru.net/api/v4"
DEFAULT_MINERU_TOKEN_ENV = "MINERU_API_TOKEN"


class MineruPDFError(RuntimeError):
    """Structured MinerU adapter error."""

    def __init__(self, error_type: str, message: str) -> None:
        super().__init__(message)
        self.error_type = error_type


@dataclass(frozen=True)
class MineruArtifacts:
    """Paths produced by a MinerU extraction run."""

    zip_file: Path
    raw_dir: Path
    manifest_file: Path
    pages_dir: Path
    markdown_file: Path | None
    content_list_file: Path | None
    model_file: Path | None
    layout_file: Path | None


class TableTextExtractor(HTMLParser):
    """Turn simple HTML table fragments from MinerU into pipe-separated text."""

    def __init__(self) -> None:
        super().__init__()
        self.rows: list[str] = []
        self.current_row: list[str] = []
        self.current_cell: list[str] = []
        self.in_cell = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag == "tr":
            self._flush_cell()
            self._flush_row()
        elif tag in {"td", "th"}:
            self._flush_cell()
            self.in_cell = True
        elif tag == "br" and self.in_cell:
            self.current_cell.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"td", "th"}:
            self._flush_cell()
        elif tag == "tr":
            self._flush_cell()
            self._flush_row()

    def handle_data(self, data: str) -> None:
        if self.in_cell:
            self.current_cell.append(data)

    def _flush_cell(self) -> None:
        if not self.in_cell:
            return
        text = normalize_whitespace("".join(self.current_cell), keep_newlines=True)
        self.current_row.append(text)
        self.current_cell = []
        self.in_cell = False

    def _flush_row(self) -> None:
        if not self.current_row:
            return
        row = " | ".join(cell for cell in self.current_row).strip()
        if row:
            self.rows.append(row)
        self.current_row = []

    def get_text(self) -> str:
        self._flush_cell()
        self._flush_row()
        return "\n".join(self.rows).strip()


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_whitespace(text: str, keep_newlines: bool = False) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if keep_newlines:
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
        return "\n".join(line for line in lines if line).strip()
    return re.sub(r"\s+", " ", text).strip()


def slugify(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    ascii_text = ascii_text.lower()
    slug = re.sub(r"[^a-z0-9._-]+", "_", ascii_text).strip("._-")
    return slug or "paper"


def load_json(path: Path) -> dict[str, Any] | list[Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def join_strings(value: Any) -> str:
    if isinstance(value, str):
        return normalize_whitespace(value, keep_newlines=True)
    if isinstance(value, list):
        parts = [join_strings(item) for item in value]
        return "\n".join(part for part in parts if part).strip()
    return ""


def html_table_to_text(html_text: str) -> str:
    parser = TableTextExtractor()
    parser.feed(html_text or "")
    parser.close()
    return parser.get_text()


def render_content_block(block: dict[str, Any]) -> str:
    block_type = str(block.get("type") or "").strip().lower()
    if block_type == "text":
        text = join_strings(block.get("text"))
        if not text:
            return ""
        level = int(block.get("text_level") or 0)
        if level > 0:
            return f"{'#' * min(level, 6)} {text}"
        return text
    if block_type == "equation":
        return join_strings(block.get("text"))
    if block_type == "table":
        parts = []
        caption = join_strings(block.get("table_caption"))
        body = html_table_to_text(str(block.get("table_body") or ""))
        footnote = join_strings(block.get("table_footnote"))
        if caption:
            parts.append(f"[TABLE CAPTION]\n{caption}")
        if body:
            parts.append(f"[TABLE BODY]\n{body}")
        if footnote:
            parts.append(f"[TABLE FOOTNOTE]\n{footnote}")
        return "\n\n".join(parts).strip()
    if block_type == "image":
        parts = []
        caption = join_strings(block.get("image_caption"))
        footnote = join_strings(block.get("image_footnote"))
        if caption:
            parts.append(f"[FIGURE CAPTION]\n{caption}")
        if footnote:
            parts.append(f"[FIGURE FOOTNOTE]\n{footnote}")
        return "\n\n".join(parts).strip()
    if block_type == "list":
        items = block.get("list_items") or []
        lines = [f"- {join_strings(item)}" for item in items if join_strings(item)]
        return "\n".join(lines).strip()
    return join_strings(block.get("content") or block.get("text"))


@register_adapter
class PDFAdapter(BaseAdapter):
    """Extract structured research-paper text from PDF files through MinerU."""

    adapter_name = "pdf"

    def __init__(self) -> None:
        self.api_base = DEFAULT_MINERU_API_BASE
        self.api_token_env = DEFAULT_MINERU_TOKEN_ENV

    def metadata(self) -> AdapterMeta:
        return AdapterMeta(
            name="pdf",
            description="PDF ingestion and structured paper extraction through MinerU",
            tools=[
                ToolSpec(
                    name="pdf_check_config",
                    description="Show MinerU PDF extraction configuration without exposing tokens.",
                    input_schema={"type": "object", "properties": {}},
                    handler=self.check_config,
                ),
                ToolSpec(
                    name="pdf_extract_mineru",
                    description=(
                        "Parse a local PDF with MinerU, save markdown/page text artifacts, "
                        "and return a manifest plus preview."
                    ),
                    input_schema={
                        "type": "object",
                        "properties": {
                            "pdf_path": {
                                "type": "string",
                                "description": "Local PDF file path to parse",
                                "minLength": 1,
                            },
                            "output_dir": {
                                "type": "string",
                                "description": "Base output directory, default outputs/mineru",
                            },
                            "out_stem": {
                                "type": "string",
                                "description": "Optional output folder name under output_dir",
                            },
                            "api_token": {
                                "type": "string",
                                "description": "Optional MinerU API token; prefer env var instead",
                            },
                            "api_token_env": {
                                "type": "string",
                                "description": (
                                    "Environment variable containing the MinerU API token"
                                ),
                                "default": DEFAULT_MINERU_TOKEN_ENV,
                            },
                            "api_base": {
                                "type": "string",
                                "description": "MinerU API base URL",
                                "default": DEFAULT_MINERU_API_BASE,
                            },
                            "model_version": {
                                "type": "string",
                                "description": "MinerU model version",
                                "default": "vlm",
                            },
                            "language": {
                                "type": "string",
                                "description": "Document language hint",
                                "default": "en",
                            },
                            "page_ranges": {
                                "type": "string",
                                "description": "Optional MinerU page ranges, for example 8-19",
                            },
                            "ocr": {
                                "type": "boolean",
                                "description": "Enable OCR for scanned PDFs",
                                "default": False,
                            },
                            "enable_formula": {
                                "type": "boolean",
                                "description": "Ask MinerU to parse formulas",
                                "default": True,
                            },
                            "enable_table": {
                                "type": "boolean",
                                "description": "Ask MinerU to parse tables",
                                "default": True,
                            },
                            "poll_interval_seconds": {
                                "type": "integer",
                                "description": "Seconds between MinerU status polls",
                                "default": 10,
                                "minimum": 1,
                                "maximum": 300,
                            },
                            "timeout_seconds": {
                                "type": "integer",
                                "description": "Maximum seconds to wait for MinerU parsing",
                                "default": 1800,
                                "minimum": 30,
                                "maximum": 7200,
                            },
                            "sync_workspace": {
                                "type": "boolean",
                                "description": (
                                    "Refresh outputs/pdf_pages and paper_sections_extract.txt"
                                ),
                                "default": True,
                            },
                            "clean_workspace_pages": {
                                "type": "boolean",
                                "description": (
                                    "Delete old outputs/pdf_pages/page_*.txt before sync"
                                ),
                                "default": True,
                            },
                            "overwrite": {
                                "type": "boolean",
                                "description": "Overwrite an existing output folder",
                                "default": True,
                            },
                            "preview_chars": {
                                "type": "integer",
                                "description": "Characters of extracted text preview to return",
                                "default": 4000,
                                "minimum": 0,
                                "maximum": 20000,
                            },
                        },
                        "required": ["pdf_path"],
                    },
                    handler=self.extract_mineru,
                ),
            ],
        )

    async def initialize(self, config: dict[str, Any] | None = None) -> None:
        cfg = config or {}
        self.api_base = cfg.get("api_base") or os.environ.get(
            "MINERU_API_BASE", DEFAULT_MINERU_API_BASE
        )
        self.api_token_env = cfg.get("api_token_env") or DEFAULT_MINERU_TOKEN_ENV

    async def check_config(self) -> dict[str, Any]:
        token_env = self.api_token_env
        return {
            "api_base": self.api_base,
            "api_token_env": token_env,
            "api_token_configured": bool(os.environ.get(token_env, "").strip()),
            "default_output_dir": str(Path("outputs") / "mineru"),
            "workspace_sync_outputs": {
                "pages_dir": str(Path("outputs") / "pdf_pages"),
                "paper_extract_file": "paper_sections_extract.txt",
            },
        }

    async def extract_mineru(
        self,
        pdf_path: str,
        output_dir: str = "",
        out_stem: str = "",
        api_token: str = "",
        api_token_env: str = DEFAULT_MINERU_TOKEN_ENV,
        api_base: str = "",
        model_version: str = "vlm",
        language: str = "en",
        page_ranges: str = "",
        ocr: bool = False,
        enable_formula: bool = True,
        enable_table: bool = True,
        poll_interval_seconds: int = 10,
        timeout_seconds: int = 1800,
        sync_workspace: bool = True,
        clean_workspace_pages: bool = True,
        overwrite: bool = True,
        preview_chars: int = 4000,
    ) -> dict[str, Any]:
        try:
            return await self._extract_mineru(
                pdf_path=pdf_path,
                output_dir=output_dir,
                out_stem=out_stem,
                api_token=api_token,
                api_token_env=api_token_env,
                api_base=api_base,
                model_version=model_version,
                language=language,
                page_ranges=page_ranges,
                ocr=ocr,
                enable_formula=enable_formula,
                enable_table=enable_table,
                poll_interval_seconds=poll_interval_seconds,
                timeout_seconds=timeout_seconds,
                sync_workspace=sync_workspace,
                clean_workspace_pages=clean_workspace_pages,
                overwrite=overwrite,
                preview_chars=preview_chars,
            )
        except MineruPDFError as exc:
            return {
                "status": "error",
                "error_type": exc.error_type,
                "message": str(exc),
            }

    async def _extract_mineru(
        self,
        pdf_path: str,
        output_dir: str,
        out_stem: str,
        api_token: str,
        api_token_env: str,
        api_base: str,
        model_version: str,
        language: str,
        page_ranges: str,
        ocr: bool,
        enable_formula: bool,
        enable_table: bool,
        poll_interval_seconds: int,
        timeout_seconds: int,
        sync_workspace: bool,
        clean_workspace_pages: bool,
        overwrite: bool,
        preview_chars: int,
    ) -> dict[str, Any]:
        path = self._require_pdf(pdf_path)
        token_env = api_token_env.strip() or self.api_token_env
        token = self._resolve_api_token(api_token, token_env)
        resolved_api_base = (api_base.strip() or self.api_base).rstrip("/")
        output_root = self._prepare_output_root(path, output_dir, out_stem, overwrite)
        artifacts = self._discover_artifacts(output_root)
        data_id = f"{slugify(out_stem or path.stem)}_{int(time.time())}"

        async with httpx.AsyncClient() as client:
            batch_id, upload_url = await self._request_upload_batch(
                client=client,
                api_base=resolved_api_base,
                token=token,
                pdf_path=path,
                model_version=model_version,
                language=language,
                data_id=data_id,
                page_ranges=page_ranges.strip(),
                enable_formula=enable_formula,
                enable_table=enable_table,
                use_ocr=ocr,
            )
            await self._upload_file(client, upload_url, path)
            result = await self._poll_batch_result(
                client=client,
                api_base=resolved_api_base,
                token=token,
                batch_id=batch_id,
                poll_interval_seconds=poll_interval_seconds,
                timeout_seconds=timeout_seconds,
            )
            zip_url = str(result.get("full_zip_url") or "").strip()
            if not zip_url:
                raise MineruPDFError(
                    "missing_result_url",
                    f"MinerU returned no full_zip_url for batch {batch_id}.",
                )
            await self._download_file(client, zip_url, artifacts.zip_file)

        self._extract_archive(artifacts.zip_file, artifacts.raw_dir)
        artifacts = self._discover_artifacts(output_root)
        page_count, heading_index = self._export_extracted_pages(artifacts)

        workspace_pages: list[Path] = []
        paper_extract_file = Path("paper_sections_extract.txt").resolve()
        if sync_workspace:
            workspace_pages = self._sync_workspace_pages(artifacts.pages_dir, clean_workspace_pages)
            self._write_paper_extract_file(
                pdf_path=path,
                artifacts=artifacts,
                batch_id=batch_id,
                data_id=data_id,
                model_version=model_version,
                language=language,
                page_count=page_count,
                heading_index=heading_index,
                paper_extract_file=paper_extract_file,
            )

        manifest = self._build_manifest(
            pdf_path=path,
            output_root=output_root,
            artifacts=artifacts,
            batch_id=batch_id,
            data_id=data_id,
            model_version=model_version,
            language=language,
            page_ranges=page_ranges.strip(),
            use_ocr=ocr,
            enable_formula=enable_formula,
            enable_table=enable_table,
            page_count=page_count,
            heading_index=heading_index,
            workspace_pages=workspace_pages,
            paper_extract_file=paper_extract_file if sync_workspace else None,
        )
        artifacts.manifest_file.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return {
            "status": "ok",
            **manifest,
            "text_preview": self._read_preview(manifest["artifacts"], preview_chars),
        }

    def _require_pdf(self, pdf_path: str) -> Path:
        path = Path(pdf_path).expanduser().resolve()
        if not path.exists() or not path.is_file():
            raise MineruPDFError("pdf_not_found", f"PDF file not found: {path}")
        if path.suffix.lower() != ".pdf":
            raise MineruPDFError("invalid_pdf", f"Expected a .pdf file: {path}")
        return path

    def _resolve_api_token(self, api_token: str, api_token_env: str) -> str:
        token = api_token.strip() or os.environ.get(api_token_env, "").strip()
        if not token:
            raise MineruPDFError(
                "missing_api_token",
                f"MinerU API token not found. Set {api_token_env} or pass api_token.",
            )
        return token

    def _prepare_output_root(
        self, pdf_path: Path, output_dir: str, out_stem: str, overwrite: bool
    ) -> Path:
        base_dir = Path(output_dir or Path("outputs") / "mineru").expanduser().resolve()
        output_root = base_dir / slugify(out_stem or pdf_path.stem)
        if output_root.exists():
            if not overwrite:
                raise MineruPDFError(
                    "output_exists",
                    f"Output directory already exists and overwrite is false: {output_root}",
                )
            shutil.rmtree(output_root)
        output_root.mkdir(parents=True, exist_ok=True)
        return output_root

    async def _request_upload_batch(
        self,
        client: httpx.AsyncClient,
        api_base: str,
        token: str,
        pdf_path: Path,
        model_version: str,
        language: str,
        data_id: str,
        page_ranges: str,
        enable_formula: bool,
        enable_table: bool,
        use_ocr: bool,
    ) -> tuple[str, str]:
        file_entry: dict[str, Any] = {"name": pdf_path.name, "data_id": data_id}
        if page_ranges:
            file_entry["page_ranges"] = page_ranges
        if use_ocr:
            file_entry["is_ocr"] = True
        payload: dict[str, Any] = {
            "files": [file_entry],
            "model_version": model_version,
            "language": language,
            "enable_formula": enable_formula,
            "enable_table": enable_table,
        }
        response = await self._api_json_request(
            client, "POST", f"{api_base}/file-urls/batch", token, payload=payload
        )
        data = response.get("data") or {}
        batch_id = str(data.get("batch_id") or "").strip()
        urls = data.get("file_urls") or []
        if not batch_id or len(urls) != 1:
            raise MineruPDFError("unexpected_api_response", "MinerU upload response is invalid.")
        return batch_id, str(urls[0])

    async def _api_json_request(
        self,
        client: httpx.AsyncClient,
        method: str,
        url: str,
        token: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
        try:
            response = await client.request(
                method,
                url,
                json=payload,
                headers=headers,
                timeout=60.0,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise MineruPDFError("api_request_failed", f"MinerU API request failed: {exc}") from exc
        try:
            data = response.json()
        except ValueError as exc:
            raise MineruPDFError("invalid_api_json", "MinerU API returned invalid JSON.") from exc
        if int(data.get("code", -1)) != 0:
            raise MineruPDFError("api_error", f"MinerU API returned an error: {data}")
        return data

    async def _upload_file(
        self,
        client: httpx.AsyncClient,
        upload_url: str,
        pdf_path: Path,
    ) -> None:
        try:
            response = await client.put(
                upload_url,
                content=pdf_path.read_bytes(),
                headers={"Content-Type": "application/pdf"},
                timeout=300.0,
            )
        except httpx.HTTPError as exc:
            raise MineruPDFError("upload_failed", f"MinerU upload failed: {exc}") from exc
        if response.status_code not in {200, 201, 204}:
            raise MineruPDFError(
                "upload_failed",
                f"MinerU upload failed with status {response.status_code}.",
            )

    async def _poll_batch_result(
        self,
        client: httpx.AsyncClient,
        api_base: str,
        token: str,
        batch_id: str,
        poll_interval_seconds: int,
        timeout_seconds: int,
    ) -> dict[str, Any]:
        start = time.monotonic()
        while True:
            response = await self._api_json_request(
                client, "GET", f"{api_base}/extract-results/batch/{batch_id}", token
            )
            results = (response.get("data") or {}).get("extract_result") or []
            if not results:
                raise MineruPDFError("unexpected_api_response", "MinerU returned no result item.")
            result = results[0]
            state = str(result.get("state") or "").strip().lower()
            if state == "done":
                return result
            if state == "failed":
                message = result.get("err_msg") or "MinerU parsing failed."
                raise MineruPDFError("parse_failed", str(message))
            if time.monotonic() - start > timeout_seconds:
                raise MineruPDFError("timeout", f"Timed out waiting for MinerU batch {batch_id}.")
            await asyncio.sleep(max(1, int(poll_interval_seconds)))

    async def _download_file(self, client: httpx.AsyncClient, url: str, dest: Path) -> None:
        try:
            response = await client.get(url, timeout=300.0)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise MineruPDFError(
                "download_failed", f"MinerU result download failed: {exc}"
            ) from exc
        dest.write_bytes(response.content)

    def _discover_artifacts(self, output_root: Path) -> MineruArtifacts:
        raw_dir = output_root / "raw"
        return MineruArtifacts(
            zip_file=output_root / "result.zip",
            raw_dir=raw_dir,
            manifest_file=output_root / "manifest.json",
            pages_dir=output_root / "pages",
            markdown_file=self._find_first(raw_dir, "full.md") or self._find_first(raw_dir, "*.md"),
            content_list_file=self._find_first(raw_dir, "*_content_list.json"),
            model_file=self._find_first(raw_dir, "*_model.json"),
            layout_file=self._find_first(raw_dir, "*_layout.pdf"),
        )

    def _find_first(self, raw_dir: Path, pattern: str) -> Path | None:
        matches = sorted(raw_dir.rglob(pattern)) if raw_dir.exists() else []
        return matches[0] if matches else None

    def _extract_archive(self, zip_file: Path, raw_dir: Path) -> None:
        raw_dir.mkdir(parents=True, exist_ok=True)
        raw_root = raw_dir.resolve()
        try:
            with zipfile.ZipFile(zip_file, "r") as archive:
                for member in archive.infolist():
                    target = (raw_dir / member.filename).resolve()
                    if target != raw_root and raw_root not in target.parents:
                        raise MineruPDFError(
                            "unsafe_archive",
                            "Refusing to extract archive member outside output dir: "
                            f"{member.filename}",
                        )
                archive.extractall(raw_dir)
        except zipfile.BadZipFile as exc:
            raise MineruPDFError(
                "invalid_archive", f"MinerU result is not a valid zip: {zip_file}"
            ) from exc

    def _export_extracted_pages(
        self, artifacts: MineruArtifacts
    ) -> tuple[int, list[dict[str, Any]]]:
        if not artifacts.content_list_file or not artifacts.content_list_file.exists():
            artifacts.pages_dir.mkdir(parents=True, exist_ok=True)
            return 0, []
        payload = load_json(artifacts.content_list_file)
        if not isinstance(payload, list):
            raise MineruPDFError(
                "invalid_content_list",
                f"Unexpected MinerU content list format: {artifacts.content_list_file}",
            )
        artifacts.pages_dir.mkdir(parents=True, exist_ok=True)
        page_map: dict[int, list[str]] = defaultdict(list)
        heading_index: list[dict[str, Any]] = []
        for entry in payload:
            if not isinstance(entry, dict):
                continue
            page_no = int(entry.get("page_idx") or 0) + 1
            rendered = render_content_block(entry)
            if rendered:
                page_map[page_no].append(rendered)
            if str(entry.get("type") or "").lower() == "text":
                level = int(entry.get("text_level") or 0)
                text = join_strings(entry.get("text"))
                if level > 0 and text:
                    heading_index.append({"page": page_no, "level": level, "text": text})
        for page_no in sorted(page_map):
            text = "\n\n".join(chunk for chunk in page_map[page_no] if chunk).strip()
            (artifacts.pages_dir / f"page_{page_no}.txt").write_text(f"{text}\n", encoding="utf-8")
        return (max(page_map.keys()) if page_map else 0), heading_index

    def _sync_workspace_pages(self, source_pages_dir: Path, clean_existing: bool) -> list[Path]:
        pdf_pages_dir = Path("outputs") / "pdf_pages"
        pdf_pages_dir.mkdir(parents=True, exist_ok=True)
        if clean_existing:
            for old_file in pdf_pages_dir.glob("page_*.txt"):
                old_file.unlink()
        published: list[Path] = []
        for source in self._sorted_page_files(source_pages_dir):
            dest = pdf_pages_dir / source.name
            shutil.copy2(source, dest)
            published.append(dest.resolve())
        return published

    def _write_paper_extract_file(
        self,
        pdf_path: Path,
        artifacts: MineruArtifacts,
        batch_id: str,
        data_id: str,
        model_version: str,
        language: str,
        page_count: int,
        heading_index: list[dict[str, Any]],
        paper_extract_file: Path,
    ) -> None:
        lines = [
            f"PDF: {pdf_path}",
            f"Generated: {now_utc_iso()}",
            f"MinerU batch_id: {batch_id}",
            f"MinerU data_id: {data_id}",
            f"Model: {model_version}",
            f"Language: {language}",
            f"Markdown: {artifacts.markdown_file if artifacts.markdown_file else ''}",
            f"Content List: {artifacts.content_list_file if artifacts.content_list_file else ''}",
            f"Page Text Dir: {artifacts.pages_dir}",
            f"Pages: {page_count}",
            "",
            "==== headings ====",
            "",
        ]
        if heading_index:
            lines.extend(
                f"page {item['page']} level {item['level']}: {item['text']}"
                for item in heading_index
            )
        else:
            lines.append("(no structured headings recovered)")
        page_files = self._sorted_page_files(artifacts.pages_dir)
        for page_file in page_files:
            page_label = page_file.stem.replace("page_", "")
            page_text = page_file.read_text(encoding="utf-8").strip()
            lines.extend(["", f"==== page {page_label} ====", "", page_text])
        if not page_files and artifacts.markdown_file and artifacts.markdown_file.exists():
            markdown_text = artifacts.markdown_file.read_text(
                encoding="utf-8", errors="ignore"
            ).strip()
            lines.extend(["", "==== full markdown ====", "", markdown_text])
        paper_extract_file.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    def _build_manifest(
        self,
        pdf_path: Path,
        output_root: Path,
        artifacts: MineruArtifacts,
        batch_id: str,
        data_id: str,
        model_version: str,
        language: str,
        page_ranges: str,
        use_ocr: bool,
        enable_formula: bool,
        enable_table: bool,
        page_count: int,
        heading_index: list[dict[str, Any]],
        workspace_pages: list[Path],
        paper_extract_file: Path | None,
    ) -> dict[str, Any]:
        return {
            "source_pdf": str(pdf_path),
            "output_root": str(output_root),
            "backend": "mineru_api",
            "batch_id": batch_id,
            "data_id": data_id,
            "generated_at_utc": now_utc_iso(),
            "model_version": model_version,
            "language": language,
            "page_ranges": page_ranges,
            "options": {
                "ocr": bool(use_ocr),
                "enable_formula": bool(enable_formula),
                "enable_table": bool(enable_table),
            },
            "artifacts": {
                "zip_file": str(artifacts.zip_file),
                "raw_dir": str(artifacts.raw_dir),
                "markdown_file": str(artifacts.markdown_file) if artifacts.markdown_file else "",
                "content_list_file": (
                    str(artifacts.content_list_file) if artifacts.content_list_file else ""
                ),
                "model_file": str(artifacts.model_file) if artifacts.model_file else "",
                "layout_file": str(artifacts.layout_file) if artifacts.layout_file else "",
                "pages_dir": str(artifacts.pages_dir),
                "workspace_pdf_pages": [str(path) for path in workspace_pages],
                "paper_extract_file": str(paper_extract_file) if paper_extract_file else "",
                "manifest_file": str(artifacts.manifest_file),
            },
            "page_count": page_count,
            "heading_count": len(heading_index),
            "headings": heading_index[:100],
        }

    def _read_preview(self, artifacts: dict[str, Any], preview_chars: int) -> str:
        if preview_chars <= 0:
            return ""
        candidates = [
            artifacts.get("paper_extract_file"),
            artifacts.get("markdown_file"),
        ]
        for value in candidates:
            path = Path(str(value or ""))
            if path.exists() and path.is_file():
                return path.read_text(encoding="utf-8", errors="ignore")[:preview_chars]
        return ""

    def _sorted_page_files(self, pages_dir: Path) -> list[Path]:
        def page_number(path: Path) -> int:
            match = re.search(r"(\d+)$", path.stem)
            return int(match.group(1)) if match else 0

        return sorted(pages_dir.glob("page_*.txt"), key=page_number)
