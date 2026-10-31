from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from typing import Dict, Any, List

from app.api.deps import get_current_user
from app.services.simulation_service import simulation_service
from app.services import report_service as rs

router = APIRouter(prefix="/reports", tags=["reports"])


def _contract_from_task(task_id: str, task: Dict[str, Any]) -> Dict[str, Any]:
    """把内存任务结果整理成结果契约的形状（与 /api/simulate/results 一致）。

    report_service 只认这套结构，因此报告与接口看到的是同一份数据。
    """
    result = task.get("result") or {}
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
        "createdAt": task.get("started_at"),
    }


def _get_task_or_404(task_id: str, current_user: Dict[str, Any]) -> Dict[str, Any]:
    task = simulation_service.get_task_status(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.get("user_id") != current_user.get("id") and current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="无权访问此任务")
    return task


def _load_meta_or_404(report_id: str, current_user: Dict[str, Any]) -> Dict[str, Any]:
    try:
        meta = rs.read_report_meta(report_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="报告不存在")
    owner = meta.get("ownerId")
    if owner is not None and owner != current_user.get("id") and current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="无权访问此报告")
    return meta


@router.post("/generate/{task_id}")
async def generate_report(
    task_id: str,
    current_user: Dict = Depends(get_current_user),
):
    """生成全年冷源站能耗仿真报告（单一标准模板）。前置条件：任务已完成。"""
    task = _get_task_or_404(task_id, current_user)

    status = task.get("status")
    if status != "completed":
        raise HTTPException(status_code=400, detail=f"任务尚未完成（当前状态：{status}），无法生成报告")

    contract = _contract_from_task(task_id, task)
    try:
        rs.validate_result(contract)
        view = rs.build_report(contract, generated_at=rs._now_iso())
        rs.validate_parameters(view, contract)
    except rs.ReportValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    html = rs.render_html(view, contract)
    report_id = rs.make_report_id(task_id)
    try:
        rs.write_report_snapshot(report_id, html, view, contract, owner_id=current_user.get("id"))
    except FileExistsError:
        raise HTTPException(status_code=409, detail="报告标识冲突，请稍后重试")

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
):
    """下载报告 HTML（原样返回，字节稳定）。"""
    _load_meta_or_404(report_id, current_user)
    try:
        path = rs.report_html_path(report_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="报告文件不存在")
    return FileResponse(path, media_type="text/html; charset=utf-8", filename=f"{report_id}.html")


@router.get("/list/{task_id}")
async def list_reports(
    task_id: str,
    current_user: Dict = Depends(get_current_user),
):
    """列出某任务的全部历史报告（D6：同一任务可有多份）。"""
    _get_task_or_404(task_id, current_user)
    reports: List[Dict[str, Any]] = rs.list_reports_for_task(task_id)
    return {"taskId": task_id, "reports": reports, "total": len(reports)}


@router.get("/{report_id}")
async def get_report_meta(
    report_id: str,
    current_user: Dict = Depends(get_current_user),
):
    """查询报告元信息（含章节清单与生成时间）。"""
    return _load_meta_or_404(report_id, current_user)
