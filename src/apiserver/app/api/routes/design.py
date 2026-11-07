"""冷源站设计工况派生接口。

前端无法运行冷机模型，COP 必须由后端算；其余流量由前端用同一公式推得。
后端仍是唯一事实源：仿真开始时后端会重新计算，不信任前端提交的值。
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from typing import Dict, Any

from app.api.deps import get_current_user
from app.services.algorithm_wrapper import algorithm_wrapper

router = APIRouter(prefix="/design", tags=["design"])


class DesignPointRequest(BaseModel):
    ts_chw_design: float = 7.0      # 冷冻水供水温度 ℃
    tr_chw_design: float = 12.0     # 冷冻水回水温度 ℃
    tr_cw_design: float = 30.0      # 冷却水回水温度 ℃
    ts_cw_design: float = 35.0      # 冷却水供水温度 ℃
    capacity_factor: float = Field(default=20.0, gt=0)
    delta_t_chw: float = 5.0
    delta_t_cw: float = 5.0


@router.post("/derive")
async def derive_design_point(
    req: DesignPointRequest,
    current_user: Dict = Depends(get_current_user),
):
    """按设计工况返回冷机 COP 与由它推导的水泵/冷却塔设计流量（大机与小机各一组）。"""
    w = algorithm_wrapper
    q_base_bch, q_base_sch = 2112.6, 1056.3
    cf = float(req.capacity_factor)
    out: Dict[str, Any] = {"capacityFactor": cf}
    for name, q_base in (("BCH", q_base_bch), ("SCH", q_base_sch)):
        q = q_base * cf
        cop = w._design_cop(q, req.tr_chw_design, req.ts_chw_design,
                            req.tr_cw_design, req.ts_cw_design)
        chw, cw = w._derive_flows(q, cop, req.delta_t_chw, req.delta_t_cw)
        out[name] = {
            "capacity": q,
            "cop": cop,
            "pumpChwFlow": chw,
            "pumpCwFlow": cw,
            "towerFlow": cw,   # 冷却塔设计水流量 = 冷却泵流量
        }
    return out
