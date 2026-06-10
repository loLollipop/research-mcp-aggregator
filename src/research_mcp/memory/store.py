"""SQLite-backed long-term memory store for research-mcp."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any
from uuid import uuid4

from research_mcp.memory.models import (
    clamp_confidence,
    dumps_json,
    loads_json,
    normalize_item_type,
    normalize_status,
    normalize_tags,
    priority_score,
    query_terms,
    utc_now,
)


class MemoryStore:
    """Persist and retrieve reusable research experience in a local SQLite file."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path).expanduser()
        self._fts_enabled = False

    @property
    def fts_enabled(self) -> bool:
        return self._fts_enabled

    def initialize(self) -> None:
        """Create database tables and optional full-text index if needed."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS memory_items (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    item_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    source_type TEXT NOT NULL DEFAULT '',
                    source_ref TEXT NOT NULL DEFAULT '',
                    project TEXT NOT NULL DEFAULT '',
                    software TEXT NOT NULL DEFAULT '',
                    problem_signature TEXT NOT NULL DEFAULT '',
                    tags_json TEXT NOT NULL DEFAULT '[]',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    success_count INTEGER NOT NULL DEFAULT 0,
                    failure_count INTEGER NOT NULL DEFAULT 0,
                    last_used_at TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS feedback_events (
                    id TEXT PRIMARY KEY,
                    item_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    feedback_type TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    note TEXT NOT NULL DEFAULT '',
                    run_ref TEXT NOT NULL DEFAULT '',
                    delta_confidence REAL NOT NULL DEFAULT 0,
                    FOREIGN KEY(item_id) REFERENCES memory_items(id)
                );

                CREATE TABLE IF NOT EXISTS simulation_runs (
                    run_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    software TEXT NOT NULL,
                    task TEXT NOT NULL,
                    status TEXT NOT NULL,
                    parameters_json TEXT NOT NULL DEFAULT '{}',
                    input_files_json TEXT NOT NULL DEFAULT '[]',
                    output_files_json TEXT NOT NULL DEFAULT '[]',
                    log_excerpt TEXT NOT NULL DEFAULT '',
                    error_signature TEXT NOT NULL DEFAULT '',
                    fix_item_ids_json TEXT NOT NULL DEFAULT '[]'
                );

                CREATE INDEX IF NOT EXISTS idx_memory_items_status
                    ON memory_items(status);
                CREATE INDEX IF NOT EXISTS idx_memory_items_type
                    ON memory_items(item_type);
                CREATE INDEX IF NOT EXISTS idx_memory_items_software
                    ON memory_items(software);
                CREATE INDEX IF NOT EXISTS idx_memory_items_project
                    ON memory_items(project);
                """
            )
            self._fts_enabled = self._ensure_fts(conn)

    def status(self) -> dict[str, Any]:
        with self._connect() as conn:
            self._sync_fts_flag(conn)
            total = conn.execute("SELECT COUNT(*) FROM memory_items").fetchone()[0]
            by_status = {
                row["status"]: row["count"]
                for row in conn.execute(
                    "SELECT status, COUNT(*) AS count FROM memory_items GROUP BY status"
                )
            }
            by_type = {
                row["item_type"]: row["count"]
                for row in conn.execute(
                    "SELECT item_type, COUNT(*) AS count FROM memory_items GROUP BY item_type"
                )
            }
        return {
            "status": "ok",
            "db_path": str(self.db_path),
            "fts_enabled": self._fts_enabled,
            "item_count": total,
            "by_status": by_status,
            "by_type": by_type,
        }

    def record(
        self,
        *,
        title: str,
        content: str,
        item_type: str = "note",
        status: str = "draft",
        confidence: float = 0.5,
        source_type: str = "user",
        source_ref: str = "",
        project: str = "",
        software: str = "",
        problem_signature: str = "",
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        clean_title = title.strip()
        clean_content = content.strip()
        if not clean_title:
            raise ValueError("Memory title cannot be empty")
        if not clean_content:
            raise ValueError("Memory content cannot be empty")

        row = self._memory_row(
            title=clean_title,
            content=clean_content,
            item_type=item_type,
            status=status,
            confidence=confidence,
            source_type=source_type,
            source_ref=source_ref,
            project=project,
            software=software,
            problem_signature=problem_signature,
            tags=tags,
            metadata=metadata,
        )

        with self._connect() as conn:
            self._insert_memory_row(conn, row)

        return self.get(row["id"]) or {}

    def _memory_row(
        self,
        *,
        title: str,
        content: str,
        item_type: str,
        status: str,
        confidence: float,
        source_type: str,
        source_ref: str,
        project: str,
        software: str,
        problem_signature: str,
        tags: list[str] | None,
        metadata: dict[str, Any] | None,
    ) -> dict[str, Any]:
        now = utc_now()
        return {
            "id": uuid4().hex,
            "created_at": now,
            "updated_at": now,
            "title": title,
            "content": content,
            "item_type": normalize_item_type(item_type),
            "status": normalize_status(status),
            "confidence": clamp_confidence(confidence),
            "source_type": source_type.strip().lower(),
            "source_ref": source_ref.strip(),
            "project": project.strip(),
            "software": software.strip(),
            "problem_signature": problem_signature.strip(),
            "tags_json": dumps_json(normalize_tags(tags)),
            "metadata_json": dumps_json(metadata or {}),
            "success_count": 0,
            "failure_count": 0,
            "last_used_at": "",
        }

    def _insert_memory_row(self, conn: sqlite3.Connection, row: dict[str, Any]) -> None:
        conn.execute(
            """
            INSERT INTO memory_items (
                id, created_at, updated_at, title, content, item_type, status,
                confidence, source_type, source_ref, project, software,
                problem_signature, tags_json, metadata_json, success_count,
                failure_count, last_used_at
            ) VALUES (
                :id, :created_at, :updated_at, :title, :content, :item_type, :status,
                :confidence, :source_type, :source_ref, :project, :software,
                :problem_signature, :tags_json, :metadata_json, :success_count,
                :failure_count, :last_used_at
            )
            """,
            row,
        )
        self._upsert_fts(conn, row)

    def get(self, item_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM memory_items WHERE id = ?", (item_id,)).fetchone()
            if row is None:
                return None
            item = self._row_to_item(row)
            events = conn.execute(
                """
                SELECT id, created_at, feedback_type, outcome, note, run_ref, delta_confidence
                FROM feedback_events
                WHERE item_id = ?
                ORDER BY created_at DESC
                """,
                (item_id,),
            ).fetchall()
            item["feedback_events"] = [dict(event) for event in events]
            return item

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        item_type: str = "",
        status: str = "",
        software: str = "",
        project: str = "",
        include_deprecated: bool = False,
    ) -> dict[str, Any]:
        clean_limit = max(1, min(int(limit), 50))
        with self._connect() as conn:
            self._sync_fts_flag(conn)
            rows = self._search_rows(
                conn,
                query=query,
                item_type=item_type,
                status=status,
                software=software,
                project=project,
                include_deprecated=include_deprecated,
            )

        scored: list[dict[str, Any]] = []
        terms = query_terms(query)
        for row, match_score in rows:
            item = self._row_to_item(row)
            if terms:
                haystack = " ".join(
                    [
                        item["title"],
                        item["content"],
                        item["problem_signature"],
                        " ".join(item["tags"]),
                    ]
                ).lower()
                match_score += sum(0.25 for term in terms if term in haystack)
            item["score"] = priority_score(item, match_score=match_score)
            scored.append(item)

        scored.sort(key=lambda item: item["score"], reverse=True)
        results = scored[:clean_limit]
        self._mark_used([item["id"] for item in results])
        return {"query": query, "count": len(results), "results": results}

    def export_context(
        self,
        query: str,
        *,
        limit: int = 5,
        software: str = "",
        project: str = "",
    ) -> dict[str, Any]:
        result = self.search(query, limit=limit, software=software, project=project)
        lines = ["# Retrieved long-term memory", ""]
        for index, item in enumerate(result["results"], start=1):
            tags = ", ".join(item["tags"])
            source = " ".join(
                part for part in [item["source_type"], item["source_ref"]] if part
            )
            lines.extend(
                [
                    f"## {index}. {item['title']}",
                    f"- id: {item['id']}",
                    "- type/status/confidence: "
                    f"{item['item_type']} / {item['status']} / {item['confidence']}",
                    f"- source: {source}",
                    f"- software/project: {item['software']} / {item['project']}",
                    f"- tags: {tags}",
                    "",
                    item["content"],
                    "",
                ]
            )
        return {"query": query, "count": result["count"], "context": "\n".join(lines).strip()}

    def update_status(
        self,
        item_id: str,
        status: str,
        *,
        confidence: float | None = None,
        note: str = "",
    ) -> dict[str, Any]:
        normalized_status = normalize_status(status)
        updates = ["status = ?", "updated_at = ?"]
        params: list[Any] = [normalized_status, utc_now()]
        if confidence is not None:
            updates.append("confidence = ?")
            params.append(clamp_confidence(confidence))
        params.append(item_id)
        with self._connect() as conn:
            cur = conn.execute(
                f"UPDATE memory_items SET {', '.join(updates)} WHERE id = ?",  # noqa: S608
                params,
            )
            if cur.rowcount == 0:
                raise KeyError(f"Unknown memory item: {item_id}")
            if note:
                self._insert_feedback(
                    conn,
                    item_id=item_id,
                    feedback_type="status_update",
                    outcome=normalized_status,
                    note=note,
                    run_ref="",
                    delta_confidence=0.0,
                )
            row = conn.execute("SELECT * FROM memory_items WHERE id = ?", (item_id,)).fetchone()
            if row is not None:
                self._upsert_fts(conn, dict(row))
        return self.get(item_id) or {}

    def record_feedback(
        self,
        item_id: str,
        *,
        feedback_type: str = "usage",
        outcome: str,
        note: str = "",
        run_ref: str = "",
        delta_confidence: float | None = None,
    ) -> dict[str, Any]:
        clean_outcome = outcome.strip().lower()
        if delta_confidence is None:
            delta_confidence = self._default_feedback_delta(clean_outcome)
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM memory_items WHERE id = ?", (item_id,)).fetchone()
            if row is None:
                raise KeyError(f"Unknown memory item: {item_id}")
            current = self._row_to_item(row)
            next_confidence = clamp_confidence(current["confidence"] + float(delta_confidence))
            success_inc = 1 if clean_outcome in {"worked", "success", "useful"} else 0
            failure_inc = 1 if clean_outcome in {"failed", "failure", "not_useful"} else 0
            conn.execute(
                """
                UPDATE memory_items
                SET confidence = ?, success_count = success_count + ?,
                    failure_count = failure_count + ?, updated_at = ?
                WHERE id = ?
                """,
                (next_confidence, success_inc, failure_inc, utc_now(), item_id),
            )
            self._insert_feedback(
                conn,
                item_id=item_id,
                feedback_type=feedback_type.strip() or "usage",
                outcome=clean_outcome,
                note=note,
                run_ref=run_ref,
                delta_confidence=float(delta_confidence),
            )
            updated = conn.execute("SELECT * FROM memory_items WHERE id = ?", (item_id,)).fetchone()
            if updated is not None:
                self._upsert_fts(conn, dict(updated))
        return self.get(item_id) or {}

    def record_simulation_run(
        self,
        *,
        software: str,
        task: str,
        status: str,
        parameters: dict[str, Any] | None = None,
        input_files: list[str] | None = None,
        output_files: list[str] | None = None,
        log_excerpt: str = "",
        error_signature: str = "",
        fix_item_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        clean_software = software.strip()
        clean_task = task.strip()
        clean_status = status.strip().lower()
        if not clean_software:
            raise ValueError("Simulation software cannot be empty")
        if not clean_task:
            raise ValueError("Simulation task cannot be empty")

        run_id = uuid4().hex
        now = utc_now()
        memory_status, memory_confidence = self._simulation_memory_status(clean_status)
        memory_row = self._memory_row(
            title=f"{clean_software} simulation run: {clean_task}",
            content=self._simulation_content(
                status=status,
                parameters=parameters or {},
                log_excerpt=log_excerpt,
                error_signature=error_signature,
            ),
            item_type="simulation_run",
            status=memory_status,
            confidence=memory_confidence,
            source_type="simulation",
            source_ref=run_id,
            project="",
            software=clean_software,
            problem_signature=error_signature,
            tags=[clean_software, clean_status, "simulation_run"],
            metadata={"run_id": run_id, "fix_item_ids": fix_item_ids or []},
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO simulation_runs (
                    run_id, created_at, software, task, status, parameters_json,
                    input_files_json, output_files_json, log_excerpt, error_signature,
                    fix_item_ids_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    now,
                    clean_software,
                    clean_task,
                    clean_status,
                    dumps_json(parameters or {}),
                    dumps_json(input_files or []),
                    dumps_json(output_files or []),
                    log_excerpt.strip(),
                    error_signature.strip(),
                    dumps_json(fix_item_ids or []),
                ),
            )
            self._insert_memory_row(conn, memory_row)
        memory = self.get(memory_row["id"]) or {}
        return {"run_id": run_id, "memory_item": memory}

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _ensure_fts(self, conn: sqlite3.Connection) -> bool:
        try:
            conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
                    item_id UNINDEXED,
                    title,
                    content,
                    tags,
                    problem_signature
                )
                """
            )
        except sqlite3.OperationalError:
            return False
        self._fts_enabled = True
        rows = conn.execute("SELECT * FROM memory_items").fetchall()
        for row in rows:
            self._upsert_fts(conn, dict(row))
        return True

    def _sync_fts_flag(self, conn: sqlite3.Connection) -> None:
        if not self._fts_enabled:
            self._fts_enabled = self._ensure_fts(conn)

    def _upsert_fts(self, conn: sqlite3.Connection, row: dict[str, Any]) -> None:
        if not self._fts_enabled:
            return
        try:
            tags = " ".join(loads_json(row.get("tags_json"), []))
            conn.execute("DELETE FROM memory_fts WHERE item_id = ?", (row["id"],))
            conn.execute(
                """
                INSERT INTO memory_fts (item_id, title, content, tags, problem_signature)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    row["id"],
                    row.get("title", ""),
                    row.get("content", ""),
                    tags,
                    row.get("problem_signature", ""),
                ),
            )
        except sqlite3.OperationalError:
            self._fts_enabled = False

    def _search_rows(
        self,
        conn: sqlite3.Connection,
        *,
        query: str,
        item_type: str,
        status: str,
        software: str,
        project: str,
        include_deprecated: bool,
    ) -> list[tuple[sqlite3.Row, float]]:
        where, params = self._filters(item_type, status, software, project, include_deprecated)
        terms = query_terms(query)
        if terms and self._fts_enabled:
            fts_query = self._fts_query(terms)
            sql = f"""
                SELECT mi.*, bm25(memory_fts) AS rank
                FROM memory_fts
                JOIN memory_items mi ON mi.id = memory_fts.item_id
                WHERE memory_fts MATCH ? {where}
            """
            try:
                return [
                    (row, max(0.0, 1.0 - abs(float(row["rank"] or 0.0))))
                    for row in conn.execute(sql, [fts_query, *params]).fetchall()
                ]
            except sqlite3.OperationalError:
                self._fts_enabled = False

        like_clauses: list[str] = []
        like_params: list[str] = []
        for term in terms:
            pattern = f"%{term}%"
            like_clauses.append(
                """
                (LOWER(title) LIKE ? OR LOWER(content) LIKE ? OR LOWER(tags_json) LIKE ?
                 OR LOWER(problem_signature) LIKE ?)
                """
            )
            like_params.extend([pattern, pattern, pattern, pattern])
        query_filter = ""
        if like_clauses:
            query_filter = " AND (" + " OR ".join(like_clauses) + ")"
        rows = conn.execute(
            f"SELECT * FROM memory_items WHERE 1=1 {where} {query_filter}",  # noqa: S608
            [*params, *like_params],
        ).fetchall()
        return [(row, 0.0) for row in rows]

    def _filters(
        self,
        item_type: str,
        status: str,
        software: str,
        project: str,
        include_deprecated: bool,
    ) -> tuple[str, list[Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if item_type:
            clauses.append("AND item_type = ?")
            params.append(normalize_item_type(item_type))
        if status:
            clauses.append("AND status = ?")
            params.append(normalize_status(status))
        elif not include_deprecated:
            clauses.append("AND status != 'deprecated'")
        if software:
            clauses.append("AND LOWER(software) = LOWER(?)")
            params.append(software)
        if project:
            clauses.append("AND project = ?")
            params.append(project)
        return " ".join(clauses), params

    def _fts_query(self, terms: list[str]) -> str:
        return " OR ".join(f'"{term.replace(chr(34), chr(34) + chr(34))}"' for term in terms)

    def _simulation_memory_status(self, status: str) -> tuple[str, float]:
        if status in {"success", "ok", "passed"}:
            return "verified", 0.7
        if status in {"failed", "failure", "error", "timeout", "crashed"}:
            return "failed", 0.25
        return "draft", 0.35

    def _mark_used(self, item_ids: list[str]) -> None:
        if not item_ids:
            return
        with self._connect() as conn:
            conn.executemany(
                "UPDATE memory_items SET last_used_at = ? WHERE id = ?",
                [(utc_now(), item_id) for item_id in item_ids],
            )

    def _insert_feedback(
        self,
        conn: sqlite3.Connection,
        *,
        item_id: str,
        feedback_type: str,
        outcome: str,
        note: str,
        run_ref: str,
        delta_confidence: float,
    ) -> None:
        conn.execute(
            """
            INSERT INTO feedback_events (
                id, item_id, created_at, feedback_type, outcome, note, run_ref,
                delta_confidence
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                uuid4().hex,
                item_id,
                utc_now(),
                feedback_type,
                outcome,
                note,
                run_ref,
                delta_confidence,
            ),
        )

    def _row_to_item(self, row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        item["tags"] = loads_json(item.pop("tags_json", "[]"), [])
        item["metadata"] = loads_json(item.pop("metadata_json", "{}"), {})
        item["confidence"] = clamp_confidence(item.get("confidence"))
        return item

    def _default_feedback_delta(self, outcome: str) -> float:
        if outcome in {"worked", "success", "useful"}:
            return 0.12
        if outcome in {"failed", "failure", "not_useful"}:
            return -0.15
        if outcome in {"approved", "verified"}:
            return 0.08
        return 0.0

    def _simulation_content(
        self,
        *,
        status: str,
        parameters: dict[str, Any],
        log_excerpt: str,
        error_signature: str,
    ) -> str:
        parts = [f"Status: {status.strip().lower()}"]
        if parameters:
            parts.append(f"Parameters: {dumps_json(parameters)}")
        if error_signature:
            parts.append(f"Error signature: {error_signature.strip()}")
        if log_excerpt:
            parts.append(f"Log excerpt:\n{log_excerpt.strip()}")
        return "\n\n".join(parts)
