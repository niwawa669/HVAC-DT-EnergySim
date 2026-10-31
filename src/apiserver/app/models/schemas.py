from pydantic import BaseModel, ConfigDict, Field
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
    load_building_r: float = 196572.0   # 数据原始单位（W），见 docs/data-contract.md
    load_coe: float = 0.001             # 量纲换算 W -> kW（口径 v1，D8）
    
    # 冷机参数
    Qr_chiller_BCH: float = 79.4808     # ÷26.58 重标定（D8/6.6）
    n_design_BCH: int = 3
    COP_chiller_BCH: float = 5.5        # 仅展示：标称值 vs 模型值校核
    Qr_chiller_SCH: float = 39.7404     # ÷26.58 重标定
    n_design_SCH: int = 1
    COP_chiller_SCH: float = 5.0        # 仅展示
    ts_chw_design: float = 7.0
    tr_chw_design: float = 12.0
    tr_cw_design: float = 30.0
    ts_cw_design: float = 35.0
    
    # 冷冻泵参数
    Gr_pump_chw_BCH: float = 3.7961     # ÷26.58 重标定
    Hr_pump_chw_BCH: float = 32.0       # 水力阻力参数，不随容量缩放
    n_pump_chw_BCH: int = 3
    Gr_pump_chw_SCH: float = 1.9007
    Hr_pump_chw_SCH: float = 32.0
    n_pump_chw_SCH: int = 1
    
    # 冷却泵参数
    Gr_pump_cw_BCH: float = 4.7442
    Hr_pump_cw_BCH: float = 30.0
    n_pump_cw_BCH: int = 3
    Gr_pump_cw_SCH: float = 2.4078
    Hr_pump_cw_SCH: float = 30.0
    n_pump_cw_SCH: int = 1
    
    # 冷却塔参数
    Gr_tower_BCH: float = 7.5245
    Pr_tower_BCH: float = 0.8277        # 仅展示：标称值 vs 模型值校核
    Hs_tower_BCH: float = 4.0
    n_tower_BCH: int = 3
    Gr_tower_SCH: float = 3.7622
    Pr_tower_SCH: float = 0.4515        # 仅展示
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
    
    # 冷机加机优先级（随装机重标定，须与 Qr_chiller_* 同口径）
    Qr_list: List[float] = [39.7404, 79.4808]
    n_design_list: List[int] = [1, 3]
    
    # 频率控制
    freq_pump_max: float = 50.0
    freq_pump_min: float = 30.0
    freq_tower_max: float = 50.0
    freq_tower_min: float = 25.0

    # ===== 模型适用范围（D11）：本期由用户配置，结果须声明其非真实训练域 =====
    applicable_range: Optional[Dict[str, float]] = None

    # ===== 碳排放口径（D10）=====
    carbon_year: Optional[str] = None
    carbon_province: Optional[str] = None

# ===== 完整配置 =====
class SimulationConfig(EquipmentConfig, ControlConfig):
    # 拒绝未映射参数（D7/6.5）：宁可在启动前报错，也不静默丢弃
    model_config = ConfigDict(extra='forbid')

# ===== 请求模型 =====
class StartSimulationRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    projectName: str = Field(min_length=1, max_length=100)
    buildingType: BuildingType
    area: float = Field(gt=0, le=1000000)
    config: SimulationConfig
    data: Dict[str, Any]
    # 数据溯源与参数快照（4.3/6.5）：前端上传时可携带，缺失则用计算结果兜底
    dataMeta: Optional[Dict[str, Any]] = None

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

# ===== 结果七区块（D4 / 7.1）=====
class EnergyBreakdown(BaseModel):
    chiller: float = 0
    pump_chw: float = 0
    pump_cw: float = 0
    tower: float = 0

class SimulationSummary(BaseModel):
    totalEnergy: float = 0
    totalCoolingLoad: float = 0        # 建筑总冷负荷（kW·h）
    totalQStation: float = 0           # 冷源站总供冷量（kW·h）
    peakCoolingLoad: float = 0         # kW
    eui: float = 0                     # kWh/m²·yr
    avgCop: float = 0                  # 冷机平均 COP
    systemEER: float = 0               # 冷源站综合能效（与冷机 COP 分离）
    totalUnmet: float = 0              # 供冷缺口（超出装机的部分）
    unmetHours: int = 0
    totalUnservedOff: float = 0        # 停机未供冷量（控制停机，非装机不足）
    carbonEmission: float = 0          # kgCO2
    area: float = 0

class WeeklyData(BaseModel):
    weekNumber: int
    weekLabel: Optional[str] = None
    weekStart: Optional[str] = None
    weekEnd: Optional[str] = None
    hours: int = 0
    totalCoolingLoad: float = 0
    peakCoolingLoad: float = 0
    totalQStation: float = 0
    totalEnergyConsumption: float = 0
    avgSystemCop: float = 0
    avgChillerCop: float = 0
    avgOutdoorTemp: float = 0
    breakdown: Optional[EnergyBreakdown] = None
    supplyGap: float = 0
    unservedWhenOff: float = 0
    unmetHours: int = 0
    progressPercentage: float = 0

class MonthlyData(BaseModel):
    month: Optional[str] = None
    hours: int = 0
    totalCoolingLoad: float = 0
    totalQStation: float = 0
    totalEnergyConsumption: float = 0
    avgChillerCop: float = 0
    systemEER: float = 0
    breakdown: Optional[EnergyBreakdown] = None
    supplyGap: float = 0

class PeakContext(BaseModel):
    timestamp: Optional[str] = None
    load: float = 0
    loadUnit: str = 'kW'
    temperature: Optional[float] = None
    humid: Optional[float] = None
    qStation: float = 0
    chillerCOP: float = 0
    systemEER: float = 0
    loadRate: float = 0
    nSCH: float = 0
    nBCH: float = 0

class SimulationMeta(BaseModel):
    fileName: Optional[str] = None
    totalRows: int = 0
    totalHours: int = 0
    startTime: Optional[str] = None
    endTime: Optional[str] = None
    confirmedRange: Optional[str] = None
    correctedOutliers: int = 0
    tDryMin: Optional[float] = None
    tDryMax: Optional[float] = None
    humidMin: Optional[float] = None
    humidMax: Optional[float] = None
    weeks: int = 0
    projectName: Optional[str] = None
    buildingType: Optional[str] = None
    area: float = 0
    caliberVersion: str = 'v1'
    loadCoe: Optional[float] = None
    carbonFactor: Dict[str, Any] = Field(default_factory=dict)
    applicableRange: Dict[str, Any] = Field(default_factory=dict)
    applicableRangeSource: Optional[str] = None
    extrapolation: Dict[str, Any] = Field(default_factory=dict)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    displayOnly: List[str] = Field(default_factory=list)
    displayOnlyDeviations: Dict[str, Any] = Field(default_factory=dict)

class UnmetHour(BaseModel):
    timestamp: Optional[str] = None
    demand: float = 0     # 需求冷负荷 kW（1 小时 → kWh）
    served: float = 0     # 实际供冷量 kW
    unmet: float = 0      # 缺口 kW
    loadRate: float = 0
    nSCH: float = 0
    nBCH: float = 0
    temperature: Optional[float] = None

class SimulationResultResponse(BaseModel):
    taskId: str
    projectId: int
    createdAt: str
    # 七个区块，始终存在
    meta: SimulationMeta = Field(default_factory=SimulationMeta)
    summary: SimulationSummary = Field(default_factory=SimulationSummary)
    weekly: List[WeeklyData] = Field(default_factory=list)
    monthly: List[MonthlyData] = Field(default_factory=list)
    breakdown: EnergyBreakdown = Field(default_factory=EnergyBreakdown)
    operating_stats: Dict[str, int] = Field(default_factory=dict)
    peak_context: PeakContext = Field(default_factory=PeakContext)
    # 逐时缺口明细：供冷缺口可定位到具体小时（空列表表示无缺口）
    unmet_hours_detail: List[UnmetHour] = Field(default_factory=list)
    # 负荷率分布（D8）：长度恒为 10，第 i 个元素为负荷率落在 [i/10, (i+1)/10) 的
    # 逐时计数，末区间含上限 1.0；各元素之和等于冷机投运小时数
    load_rate_histogram: List[int] = Field(default_factory=lambda: [0] * 10)