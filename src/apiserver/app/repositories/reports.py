"""报告索引仓储（D5）：文件是唯一产物，库是索引。"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.orm import Report


def _sha256_file(path: Path) -> Optional[str]:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with open(path, "rb") as fp:
        for chunk in iter(lambda: fp.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_size(path: Path) -> Optional[int]:
    try:
        return path.stat().st_size if path.is_file() else None
    except OSError:
        return None


async def insert(
    session: AsyncSession,
    *,
    report_id: str,
    task_id: Optional[str],
    owner_id: Optional[int],
    meta: Dict[str, Any],
    directory: str,
) -> Report:
    base = Path(directory)
    html_path = base / "report.html"
    row = Report(
        report_id=report_id,
        task_id=task_id,
        owner_id=owner_id,
        report_version=meta.get("reportVersion"),
        caliber_version=meta.get("caliberVersion"),
        generated_at=meta.get("generatedAt"),
        meta_payload=meta,
        chapters=meta.get("chapterOrder"),
        chapter_titles=meta.get("chapterTitles"),
        html_path=str(html_path),
        result_path=str(base / "result.json"),
        meta_path=str(base / "meta.json"),
        html_sha256=_sha256_file(html_path),
        html_size=_file_size(html_path),
        artifact_state="ready" if html_path.is_file() else "missing",
    )
    session.add(row)
    await session.flush()
    return row


async def get(session: AsyncSession, report_id: str) -> Optional[Report]:
    return await session.get(Report, report_id)


async def list_by_task(session: AsyncSession, task_id: str) -> List[Report]:
    stmt = (
        select(Report)
        .where(Report.task_id == task_id)
        .order_by(Report.generated_at.desc())
    )
    return list((await session.execute(stmt)).scalars().all())


def serialize_meta(row: Report) -> Dict[str, Any]:
    if row.meta_payload:
        return dict(row.meta_payload)
    return {
        "reportId": row.report_id,
        "taskId": row.task_id,
        "ownerId": row.owner_id,
        "reportVersion": row.report_version,
        "caliberVersion": row.caliber_version,
        "generatedAt": row.generated_at,
        "chapterOrder": row.chapters,
        "chapterTitles": row.chapter_titles,
    }


def summarize(row: Report) -> Dict[str, Any]:
    return {
        "reportId": row.report_id,
        "generatedAt": row.generated_at,
        "caliberVersion": row.caliber_version,
        "reportVersion": row.report_version,
    }


def _read_meta(path: Path) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


async def reconcile_from_disk(session: AsyncSession) -> Dict[str, int]:
    """启动对账：产物 -> 索引补插；索引 -> 产物存在性标记。"""
    base = Path(settings.reports_dir)
    imported = scanned = 0
    if base.is_dir():
        for entry in sorted(base.iterdir()):
            if not entry.is_dir() or entry.name.endswith(".tmp"):
                continue
            meta_path = entry / "meta.json"
            if not meta_path.is_file():
                continue
            scanned += 1
            meta = _read_meta(meta_path)
            if meta is None:
                continue
            report_id = meta.get("reportId") or entry.name
            html_path = entry / "report.html"
            row = await session.get(Report, report_id)
            if row is None:
                await insert(
                    session,
                    report_id=report_id,
                    task_id=meta.get("taskId"),
                    owner_id=meta.get("ownerId"),
                    meta=meta,
                    directory=str(entry),
                )
                imported += 1
            else:
                row.meta_payload = meta
                row.html_path = str(html_path)
                row.result_path = str(entry / "result.json")
                row.meta_path = str(meta_path)
                row.html_sha256 = _sha256_file(html_path)
                row.html_size = _file_size(html_path)
                row.artifact_state = "ready" if html_path.is_file() else "missing"

    rows = list((await session.execute(select(Report))).scalars().all())
    missing = 0
    for row in rows:
        exists = bool(row.html_path) and os.path.isfile(row.html_path)
        row.artifact_state = "ready" if exists else "missing"
        if not exists:
            missing += 1
    await session.flush()
    return {"scanned": scanned, "imported": imported, "missing": missing, "total": len(rows)}
