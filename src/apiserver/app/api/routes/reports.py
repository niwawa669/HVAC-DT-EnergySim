from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from typing import Dict, Any, List
import json
import shutil
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.repositories import reports as reports_repo
from app.repositories import results as results_repo
from app.repositories import tasks as tasks_repo
from app.services import report_service as rs

router = APIRouter(prefix="/reports", tags=["reports"])


def _contract_from_result(task_id: str, task, payload: Dict[str, Any]) -> Dict[str, Any]:
    """把持久化的七区块结果整理成结果契约的形状（与 /api/simulate/results 一致）。"""
    result = payload or {}
    summary = result.get("summary") or {}
    meta = dict(result.get("meta") or {})
    # 枚举值统一落成字符串，避免报告里出现 "BuildingType.OFFICE" 这类形式
    for key in ("buildingType", "projectName"):
        if key in meta:
            meta[key] = getattr(meta[key], "value", meta[key])
    return {
        "taskId": task_id,
        "meta": meta,
        "summary": summary,
        "breakdown": summary.get("breakdown") or {},
        "weekly": result.get("weekly_data") or [],
        "monthly": result.get("monthly_data") or [],
        "operating_stats": summary.get("operatingStats") or {},
        "peak_context": summary.get("peakContext") or {},
        "unmet_hours_detail": result.get("unmet_hours_detail") or [],
        "load_rate_histogram": summary.get("loadRateHistogram") or [],
        "createdAt": task.started_at.isoformat() if task.started_at else None,
    }


async def _get_task_or_404(db: AsyncSession, task_id: str, current_user: Dict[str, Any]):
    task = await tasks_repo.get(db, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.user_id != current_user.get("id") and current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="无权访问此任务")
    return task


async def _get_report_or_404(
    db: AsyncSession, report_id: str, current_user: Dict[str, Any]
):
    row = await reports_repo.get(db, report_id)
    if row is None:
        raise HTTPException(status_code=404, detail="报告不存在")
    task = await tasks_repo.get(db, row.task_id) if row.task_id else None
    owner = task.user_id if task is not None else row.owner_id
    if owner is not None and owner != current_user.get("id") and current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="无权访问此报告")
    return row


@router.post("/generate/{task_id}")
async def generate_report(
    task_id: str,
    current_user: Dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """生成全年冷源站能耗仿真报告（单一标准模板）。前置条件：任务已完成且有结果。"""
    task = await _get_task_or_404(db, task_id, current_user)

    status = task.status
    if status != "completed":
        raise HTTPException(status_code=400, detail=f"任务尚未完成（当前状态：{status}），无法生成报告")

    payload = await results_repo.load_payload(db, task_id)
    if not payload:
        raise HTTPException(status_code=400, detail="结果不存在，无法生成报告")

    contract = _contract_from_result(task_id, task, payload)
    try:
        rs.validate_result(contract)
        view = rs.build_report(contract, generated_at=rs._now_iso())
        rs.validate_parameters(view, contract)
    except rs.ReportValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    html = rs.render_html(view, contract)
    report_id = rs.make_report_id(task_id)
    try:
        directory = rs.write_report_snapshot(
            report_id, html, view, contract, owner_id=current_user.get("id")
        )
    except FileExistsError:
        raise HTTPException(status_code=409, detail="报告标识冲突，请稍后重试")

    # 先产物、后索引；索引失败则清理本次产物，避免"有产物无索引"的半成品
    try:
        meta = json.loads((Path(directory) / "meta.json").read_text(encoding="utf-8"))
        await reports_repo.insert(
            db,
            report_id=report_id,
            task_id=task_id,
            owner_id=current_user.get("id"),
            meta=meta,
            directory=directory,
        )
        await db.commit()
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        shutil.rmtree(directory, ignore_errors=True)
        print(f"❌ 报告索引写入失败，已清理产物: {report_id}: {exc}")
        raise HTTPException(status_code=500, detail="报告索引写入失败，已清理本次产物")

    return {
        "reportId": report_id,
        "taskId": task_id,
        "status": "ready",
        "generatedAt": view.get("generatedAt"),
        "caliberVersion": view.get("caliberVersion"),
        "chapters": view.get("chapterOrder"),
        "downloadUrl": f"/api/reports/download/{report_id}",
    }


@router.get("/download/{report_id}")
async def download_report(
    report_id: str,
    current_user: Dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """下载报告 HTML（原样返回，字节稳定）。"""
    row = await _get_report_or_404(db, report_id, current_user)

    path = Path(row.html_path or "")
    if not path.is_file():
        row.artifact_state = "missing"
        await db.commit()
        raise HTTPException(
            status_code=404,
            detail=f"报告产物缺失（可能已被删除）：{report_id}",
        )
    return FileResponse(str(path), media_type="text/html; charset=utf-8", filename=f"{report_id}.html")


@router.get("/list/{task_id}")
async def list_reports(
    task_id: str,
    current_user: Dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """列出某任务的全部历史报告（D6：同一任务可有多份）。

    历史报告的 task 可能早已不存在（改动前的内存任务），此时按报告归属校验。
    """
    rows = await reports_repo.list_by_task(db, task_id)
    task = await tasks_repo.get(db, task_id)
    if task is not None:
        if task.user_id != current_user.get("id") and current_user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="无权访问此任务")
    elif rows:
        owners = {row.owner_id for row in rows if row.owner_id is not None}
        if owners and current_user.get("id") not in owners and current_user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="无权访问此报告")
    else:
        raise HTTPException(status_code=404, detail="任务不存在")
    reports: List[Dict[str, Any]] = [reports_repo.summarize(row) for row in rows]
    return {"taskId": task_id, "reports": reports, "total": len(reports)}


@router.get("/{report_id}")
async def get_report_meta(
    report_id: str,
    current_user: Dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查询报告元信息（含章节清单与生成时间）。"""
    row = await _get_report_or_404(db, report_id, current_user)
    return reports_repo.serialize_meta(row)
