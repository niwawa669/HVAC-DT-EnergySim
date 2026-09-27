from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum

# ===== 枚举类型 =====
class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class BuildingType(str, Enum):
    OFFICE = "office"
    COMMERCIAL = "commercial"
    RESIDENTIAL = "residential"
    HOSPITAL = "hospital"
    INDUSTRIAL = "industrial"

# ===== 设备选型参数 =====
class EquipmentConfig(BaseModel):
    # 建筑负荷
    load_building_r: float = 196572.0
    load_coe: float = 0.0376
    coe: float = 0.8333
    coe_tower_efficience: float = 0.95
    
    # 冷机参数
    Qr_chiller_BCH: float = 2112.6
    n_design_BCH: int = 3
    COP_chiller_BCH: float = 5.5
    Qr_chiller_SCH: float = 1056.3
    n_design_SCH: int = 1
    COP_chiller_SCH: float = 5.0
    ts_chw_design: float = 7.0
    tr_chw_design: float = 12.0
    tr_cw_design: float = 30.0
    ts_cw_design: float = 35.0
    
    # 冷冻泵参数
    Gr_pump_chw_BCH: float = 100.9
    Hr_pump_chw_BCH: float = 32.0
    n_pump_chw_BCH: int = 3
    Gr_pump_chw_SCH: float = 50.5
    Hr_pump_chw_SCH: float = 32.0
    n_pump_chw_SCH: int = 1
    
    # 冷却泵参数
    Gr_pump_cw_BCH: float = 126.1
    Hr_pump_cw_BCH: float = 30.0
    n_pump_cw_BCH: int = 3
    Gr_pump_cw_SCH: float = 64.0
    Hr_pump_cw_SCH: float = 30.0
    n_pump_cw_SCH: int = 1
    
    # 冷却塔参数
    Gr_tower_BCH: float = 200.0
    Pr_tower_BCH: float = 22.0
    Hs_tower_BCH: float = 4.0
    n_tower_BCH: int = 3
    Gr_tower_SCH: float = 100.0
    Pr_tower_SCH: float = 12.0
    Hs_tower_SCH: float = 3.8
    n_tower_SCH: int = 1
    
    # 管道压降
    Hr_pt: float = 20.0
    Hr_chiller_chw_BCH: float = 6.0
    Hr_chiller_cw_BCH: float = 7.0
    Hr_chiller_chw_SCH: float = 5.0
    Hr_chiller_cw_SCH: float = 6.0

# ===== 群控控制参数 =====
class ControlConfig(BaseModel):
    # 温度控制
    ta_dry_r: float = 31.7
    ta_wet_r: float = 23.47
    ts_chw_set: float = 7.0
    delta_t_chw: float = 5.0
    delta_t_cw: float = 5.0
    tr_cw_min: float = 20.0
    approach_set: float = 3.0
    
    # 负荷控制
    load_up: float = 0.9
    load_min: float = 0.3
    
    # 冷机加机优先级
    Qr_list: List[float] = [1056.3, 2112.6]
    n_design_list: List[int] = [1, 3]
    
    # 频率控制
    freq_pump_max: float = 50.0
    freq_pump_min: float = 30.0
    freq_tower_max: float = 50.0
    freq_tower_min: float = 25.0

# ===== 完整配置 =====
class SimulationConfig(EquipmentConfig, ControlConfig):
    pass

# ===== 请求模型 =====
class StartSimulationRequest(BaseModel):
    projectName: str = Field(min_length=1, max_length=100)
    buildingType: BuildingType
    area: float = Field(ge=100, le=1000000)
    config: SimulationConfig
    data: Dict[str, Any]

class LoginRequest(BaseModel):
    username: str
    password: str

# ===== 响应模型 =====
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Dict[str, Any]

class TaskResponse(BaseModel):
    taskId: str
    status: TaskStatus
    progress: int = 0
    currentWeek: int = 0
    totalWeeks: int = 52
    startedAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None
    message: Optional[str] = None

class SimulationSummary(BaseModel):
    totalEnergy: float = 0
    totalCoolingLoad: float = 0
    totalQStation: float = 0
    peakCoolingLoad: float = 0
    eui: float = 0
    avgCop: float = 0
    carbonEmission: float = 0

class WeeklyData(BaseModel):
    weekNumber: int
    totalCoolingLoad: float = 0
    peakCoolingLoad: float = 0
    totalQStation: float = 0
    totalEnergyConsumption: float = 0
    avgSystemCop: float = 0
    avgOutdoorTemp: float = 0

class SimulationResultResponse(BaseModel):
    taskId: str
    projectId: int
    summary: SimulationSummary
    weeklyData: List[WeeklyData]
    createdAt: str