"""Local LaTeX adapter for manuscript validation and compilation."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

from research_mcp.adapters import AdapterMeta, BaseAdapter, ToolSpec, register_adapter


@register_adapter
class LatexAdapter(BaseAdapter):
    """Compile and validate local LaTeX projects without external MCP servers."""

    adapter_name = "latex"

    def __init__(self) -> None:
        self.latex_cmd = "latexmk"
        self.timeout_seconds = 300

    def metadata(self) -> AdapterMeta:
        return AdapterMeta(
            name="latex",
            description="Local LaTeX manuscript tools using latexmk or pdflatex",
            tools=[
                ToolSpec(
                    name="latex_check_config",
                    description="Show configured LaTeX command and timeout.",
                    input_schema={"type": "object", "properties": {}},
                    handler=self.check_config,
                ),
                ToolSpec(
                    name="latex_validate_project",
                    description="Validate a LaTeX main file and referenced local assets.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "main_tex": {
                                "type": "string",
                                "description": "Path to main .tex file",
                                "minLength": 1,
                            },
                        },
                        "required": ["main_tex"],
                    },
                    handler=self.validate_project,
                ),
                ToolSpec(
                    name="latex_compile",
                    description="Compile a local LaTeX project with the configured LaTeX command.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "main_tex": {
                                "type": "string",
                                "description": "Path to main .tex file",
                                "minLength": 1,
                            },
                            "output_dir": {
                                "type": "string",
                                "description": "Optional output directory",
                            },
                            "timeout_seconds": {
                                "type": "integer",
                                "description": "Timeout seconds",
                                "minimum": 1,
                            },
                        },
                        "required": ["main_tex"],
                    },
                    handler=self.compile,
                ),
                ToolSpec(
                    name="latex_create_minimal_project",
                    description="Create a minimal local LaTeX project with a main.tex file.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "project_dir": {
                                "type": "string",
                                "description": "Directory to create/use",
                                "minLength": 1,
                            },
                            "title": {
                                "type": "string",
                                "description": "Document title",
                                "minLength": 1,
                            },
                            "author": {"type": "string", "description": "Document author"},
                        },
                        "required": ["project_dir", "title"],
                    },
                    handler=self.create_minimal_project,
                ),
            ],
        )

    async def initialize(self, config: dict[str, Any] | None = None) -> None:
        cfg = config or {}
        self.latex_cmd = cfg.get("latex_cmd") or os.environ.get("LATEX_CMD", "latexmk")
        self.timeout_seconds = int(
            cfg.get("timeout_seconds") or os.environ.get("LATEX_TIMEOUT_SECONDS", "300")
        )

    async def check_config(self) -> dict[str, Any]:
        return {
            "latex_cmd": self.latex_cmd,
            "timeout_seconds": self.timeout_seconds,
            "env": {
                "LATEX_CMD": os.environ.get("LATEX_CMD", ""),
                "LATEX_TIMEOUT_SECONDS": os.environ.get("LATEX_TIMEOUT_SECONDS", ""),
            },
        }

    async def validate_project(self, main_tex: str) -> dict[str, Any]:
        path = self._require_tex(main_tex)
        content = path.read_text(encoding="utf-8")
        referenced_assets = self._referenced_assets(content)
        missing_assets = [
            asset for asset in referenced_assets if not self._asset_exists(path.parent, asset)
        ]
        return {
            "main_tex": str(path),
            "project_dir": str(path.parent),
            "has_documentclass": "\\documentclass" in content,
            "has_begin_document": "\\begin{document}" in content,
            "referenced_assets": referenced_assets,
            "missing_assets": missing_assets,
            "valid": "\\documentclass" in content
            and "\\begin{document}" in content
            and not missing_assets,
        }

    async def compile(
        self,
        main_tex: str,
        output_dir: str = "",
        timeout_seconds: int = 0,
    ) -> dict[str, Any]:
        path = self._require_tex(main_tex)
        args = self._compile_args(path, output_dir)
        return await self._run(args, path.parent, timeout_seconds or self.timeout_seconds)

    async def create_minimal_project(
        self,
        project_dir: str,
        title: str,
        author: str = "",
    ) -> dict[str, Any]:
        directory = Path(project_dir).expanduser().resolve()
        directory.mkdir(parents=True, exist_ok=True)
        main_tex = directory / "main.tex"
        author_line = f"\\author{{{author}}}\n" if author else ""
        main_tex.write_text(
            "\\documentclass{article}\n"
            "\\usepackage[margin=1in]{geometry}\n"
            f"\\title{{{title}}}\n"
            f"{author_line}"
            "\\begin{document}\n"
            "\\maketitle\n"
            "\\section{Introduction}\n"
            "Write your manuscript here.\n"
            "\\end{document}\n",
            encoding="utf-8",
        )
        return {"project_dir": str(directory), "main_tex": str(main_tex)}

    def _require_tex(self, main_tex: str) -> Path:
        path = Path(main_tex).expanduser().resolve()
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"LaTeX file not found: {path}")
        if path.suffix.lower() != ".tex":
            raise ValueError(f"Expected a .tex file: {path}")
        return path

    def _compile_args(self, main_tex: Path, output_dir: str) -> list[str]:
        if "latexmk" in Path(self.latex_cmd).name.lower():
            args = [self.latex_cmd, "-pdf", "-interaction=nonstopmode", str(main_tex)]
            if output_dir:
                out = Path(output_dir).expanduser().resolve()
                out.mkdir(parents=True, exist_ok=True)
                args.insert(1, f"-outdir={out}")
            return args
        args = [self.latex_cmd, "-interaction=nonstopmode"]
        if output_dir:
            out = Path(output_dir).expanduser().resolve()
            out.mkdir(parents=True, exist_ok=True)
            args.extend(["-output-directory", str(out)])
        args.append(str(main_tex))
        return args

    def _referenced_assets(self, content: str) -> list[str]:
        import re

        assets: list[str] = []
        for command in ("includegraphics", "input", "include", "bibliography"):
            assets.extend(re.findall(rf"\\{command}(?:\[[^\]]*\])?\{{([^}}]+)\}}", content))
        return sorted(dict.fromkeys(asset.strip() for asset in assets if asset.strip()))

    def _asset_exists(self, project_dir: Path, asset: str) -> bool:
        path = project_dir / asset
        if path.exists():
            return True
        if Path(asset).suffix:
            return False
        candidates = [
            project_dir / f"{asset}.tex",
            project_dir / f"{asset}.bib",
            project_dir / f"{asset}.pdf",
            project_dir / f"{asset}.png",
            project_dir / f"{asset}.jpg",
            project_dir / f"{asset}.jpeg",
            project_dir / f"{asset}.svg",
        ]
        return any(candidate.exists() for candidate in candidates)

    async def _run(self, args: list[str], cwd: Path, timeout_seconds: int) -> dict[str, Any]:
        proc = await asyncio.create_subprocess_exec(
            *args,
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_seconds)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return {
                "status": "timeout",
                "command": args,
                "cwd": str(cwd),
                "timeout_seconds": timeout_seconds,
            }
        return {
            "status": "ok" if proc.returncode == 0 else "failed",
            "returncode": proc.returncode,
            "command": args,
            "cwd": str(cwd),
            "stdout": stdout.decode(errors="replace")[-8000:],
            "stderr": stderr.decode(errors="replace")[-8000:],
        }
