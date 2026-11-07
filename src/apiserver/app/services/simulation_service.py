"""仿真服务：后台任务执行、进度落库与 WebSocket 推送（D7/D8）。

业务状态不再保存在进程内存：任务与结果由仓储读写，
本服务只保留"连接中的 WebSocket"这类天然瞬态数据。
"""
from __future__ import annotations

import asyncio
import json
import traceback
from datetime import datetime
from typing import Any, Dict, Optional

from app.db.session import session_scope
from app.repositories import results as results_repo
from app.repositories import tasks as tasks_repo
from app.services.algorithm_wrapper import algorithm_wrapper

HISTOGRAM_BINS = 10


class SimulationService:
    def __init__(self):
        self.websocket_connections: Dict[str, Any] = {}

    # ===== WebSocket =====
    def register_websocket(self, task_id: str, websocket) -> None:
        self.websocket_connections[task_id] = websocket
        print(f"📝 WebSocket 注册成功: {task_id}, 当前连接数: {len(self.websocket_connections)}")

    def unregister_websocket(self, task_id: str) -> None:
        if task_id in self.websocket_connections:
            del self.websocket_connections[task_id]
            print(f"📝 WebSocket 已注销: {task_id}, 剩余连接数: {len(self.websocket_connections)}")

    async def _send_websocket_message(self, task_id: str, message: Dict) -> bool:
        ws = self.websocket_connections.get(task_id)
        if ws is None:
            print(f"⚠️ WebSocket 连接不存在: {task_id}")
            return False
        try:
            await ws.send_text(json.dumps(message))
            print(f"📤 发送 WebSocket 消息到 {task_id}: {message.get('type')}")
            return True
        except Exception as exc:  # noqa: BLE001
            print(f"❌ 发送 WebSocket 消息失败: {exc}")
            self.websocket_connections.pop(task_id, None)
            return False

    # ===== 任务执行 =====
    def start_task(self, task_id: str, request_data: Dict[str, Any]) -> None:
        """把任务提交到事件循环（调用方已保证任务行落库）。"""
        asyncio.create_task(self.run_task(task_id, request_data))

    async def run_task(self, task_id: str, request_data: Dict[str, Any]) -> None:
        """执行一次仿真：进度落库、每周检查取消、结果与终态原子提交。"""
        data = request_data.get("data") or {}
        rows = data.get("rows") or []
        config = request_data.get("config") or {}
        area = request_data.get("area", 2931000.0)

        # 算法按"首列是时间戳"取列，JSON 往返可能打乱字典键序：按表头顺序重建行
        data_headers = data.get("headers") or []
        if data_headers and rows and isinstance(rows[0], dict):
            rows = [{str(h): row.get(h) for h in data_headers} for row in rows]

        async with session_scope() as session:
            task = await tasks_repo.get(session, task_id)
            if task is None:
                print(f"⚠️ 任务不存在，停止执行: {task_id}")
                return
            if task.status == "cancelled":
                return
            await tasks_repo.set_status(session, task_id, "running", progress=0)
            data_meta = dict(task.data_meta or {})
            project_name = task.project_name
            building_type = task.building_type

        run_meta = {
            "fileName": data_meta.get("fileName"),
            "totalRows": data_meta.get("totalRows", len(rows)),
            "confirmedRange": data_meta.get("confirmedRange"),
            "correctedOutliers": data_meta.get("correctedOutliers", 0),
            "projectName": project_name,
            "buildingType": building_type,
            "area": area,
            "parameters": config,
        }

        await self._send_websocket_message(task_id, {
            "type": "started",
            "message": "仿真开始计算...",
        })

        sink: Dict[str, Any] = {}
        try:
            print(f"🔄 开始执行仿真任务: {task_id}, 数据行数={len(rows)}, 面积={area} m²")

            for week_result in algorithm_wrapper.run_simulation_streaming(
                data=rows,
                config=config,
                area=area,
                meta=run_meta,
                result_sink=sink,
            ):
                week_number = int(week_result.get("weekNumber", 0) or 0)
                progress = int(round(week_result.get("progressPercentage", 0)))

                async with session_scope() as session:
                    status = await tasks_repo.update_progress(
                        session, task_id, progress=progress, current_week=week_number
                    )
                if status is None:
                    print(f"⚠️ 任务行已不存在，停止执行: {task_id}")
                    return
                if status == "cancelled":
                    print(f"🛑 任务已取消，停止执行: {task_id}")
                    return

                await self._send_websocket_message(task_id, {
                    "type": "progress",
                    "data": {
                        "weekNumber": week_number,
                        "progressPercentage": progress,
                        "totalCoolingLoad": week_result.get("totalCoolingLoad", 0),
                        "peakCoolingLoad": week_result.get("peakCoolingLoad", 0),
                        "totalQStation": week_result.get("totalQStation", 0),
                        "totalEnergyConsumption": week_result.get("totalEnergyConsumption", 0),
                        "avgSystemCop": week_result.get("avgSystemCop", 0),
                        "avgOutdoorTemp": week_result.get("avgOutdoorTemp", 0),
                    },
                })
                await asyncio.sleep(0.02)

            summary = sink.get("summary") or algorithm_wrapper.get_last_summary()
            weekly = sink.get("weekly_data") or algorithm_wrapper.get_last_weekly_data()
            monthly = sink.get("monthly_data") or algorithm_wrapper.get_last_monthly_data()
            meta = sink.get("meta") or algorithm_wrapper.get_last_meta()
            unmet = sink.get("unmet_hours_detail")
            if unmet is None:
                unmet = algorithm_wrapper.get_last_unmet_hours()

            payload = {
                "meta": meta,
                "summary": summary,
                "weekly_data": weekly,
                "monthly_data": monthly,
                "unmet_hours_detail": unmet,
            }

            async with session_scope() as session:
                try:
                    await results_repo.save_with_status(session, task_id, payload)
                except results_repo.TaskCancelled:
                    print(f"🛑 任务已取消，丢弃结果: {task_id}")
                    return

            await self._send_websocket_message(task_id, {
                "type": "completed",
                "summary": {
                    "totalEnergy": summary.get("totalEnergy", 0),
                    "totalCoolingLoad": summary.get("totalCoolingLoad", 0),
                    "totalQStation": summary.get("totalQStation", 0),
                    "peakCoolingLoad": summary.get("peakCoolingLoad", 0),
                    "eui": summary.get("eui", 0),
                    "avgCop": summary.get("avgCop", 0),
                    "carbonEmission": summary.get("carbonEmission", 0),
                    "area": summary.get("area", 0),
                },
            })
            print(f"✅ 仿真任务 {task_id} 完成")

        except Exception as exc:  # noqa: BLE001
            error_msg = str(exc)
            print(f"❌ 仿真任务 {task_id} 失败: {error_msg}")
            traceback.print_exc()
            async with session_scope() as session:
                task = await tasks_repo.get(session, task_id)
                if task is not None and task.status != "cancelled":
                    await tasks_repo.set_status(
                        session, task_id, "failed", error=error_msg,
                        progress=task.progress,
                    )
            await self._send_websocket_message(task_id, {"type": "failed", "error": error_msg})


# 单例
simulation_service = SimulationService()
