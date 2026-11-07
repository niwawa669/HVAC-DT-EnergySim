from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import List, Dict, Any, Optional, Literal
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
    load_building_r: float = 303067.16  # 建筑设计峰值负荷 kW（缺省取示例数据峰值）
    capacity_factor: float = Field(default=20.0, gt=0)  # 冷机容量放大系数（D4）：实际单机容量 = 基准容量 × 该系数
    
    # 冷机参数
    Qr_chiller_BCH: float = 2112.6      # 基准额定冷量 kW（= 模型参考容量）
    n_design_BCH: int = 7
    Qr_chiller_SCH: float = 1056.3      # 基准额定冷量 kW（大机的一半）
    n_design_SCH: int = 1
    ts_chw_design: float = 7.0
    tr_chw_design: float = 12.0
    tr_cw_design: float = 30.0
    ts_cw_design: float = 35.0
    
    # 冷冻泵参数
    Hr_pump_chw_BCH: float = 32.0       # 水力阻力参数，不随容量缩放
    n_pump_chw_BCH: int = 7
    Hr_pump_chw_SCH: float = 32.0
    n_pump_chw_SCH: int = 1
    
    # 冷却泵参数
    Hr_pump_cw_BCH: float = 30.0
    n_pump_cw_BCH: int = 7
    Hr_pump_cw_SCH: float = 30.0
    n_pump_cw_SCH: int = 1
    
    # 冷却塔参数
    Pr_tower_BCH: float = 440.0         # 塔设计功率 kW（用户输入，按设计点归一参与计算）
    Hs_tower_BCH: float = 4.0
    n_tower_BCH: int = 7
    Pr_tower_SCH: float = 240.0         # 塔设计功率 kW（用户输入）
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
    
    # 冷机加机优先级（须与 Qr_chiller_* / n_design_* 同口径）
    Qr_list: List[float] = [1056.3, 2112.6]
    n_design_list: Optional[List[int]] = None
    
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

    @model_validator(mode='after')
    def _check_staging_list(self):
        """加机优先级序列必须与实际台数一致（参数生效原则）。

        允许省略：省略时由台数推导，见 algorithm_wrapper。显式给出且与台数不符时拒绝，
        否则群控会按序列里的台数投运——比实际台数少，且界面上看不出任何异常。
        """
        provided = self.n_design_list
        if provided is None:
            return self
        expected = [self.n_design_SCH, self.n_design_BCH]
        if list(provided) != expected:
            raise ValueError(
                f"加机优先级序列 n_design_list={list(provided)} 与冷机台数 "
                f"[n_design_SCH, n_design_BCH]={expected} 不一致；"
                f"两者不一致会导致群控按错误台数投运。"
            )
        return self

# ===== 请求模型 =====
class StartSimulationRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    projectName: str = Field(min_length=1, max_length=100)
    buildingType: BuildingType
    area: float = Field(gt=0, le=10000000)  # 上限 1000 万 m²，覆盖区域级项目
    config: SimulationConfig
    data: Dict[str, Any]
    # 数据溯源与参数快照（4.3/6.5）：前端上传时可携带，缺失则用计算结果兜底
    dataMeta: Optional[Dict[str, Any]] = None
    # 可选关联项目（D14）：不传时为未关联，结果里的 projectId 返回 0
    projectId: Optional[int] = Field(default=None, ge=1)

class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')

    name: str = Field(min_length=1, max_length=128)
    buildingType: Optional[str] = Field(default=None, max_length=32)
    area: Optional[float] = Field(default=None, gt=0)
    status: Optional[str] = Field(default=None, max_length=32)


class UserCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')

    username: str = Field(min_length=3, max_length=64, pattern=r'^[A-Za-z0-9_.-]+$')
    password: str = Field(min_length=6, max_length=72)
    email: Optional[str] = Field(default=None, max_length=255)
    role: Literal['admin', 'engineer'] = 'engineer'


class UserUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')

    email: Optional[str] = Field(default=None, max_length=255)
    role: Optional[Literal['admin', 'engineer']] = None
    isActive: Optional[bool] = None


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')

    email: Optional[str] = Field(default=None, max_length=255)


class PasswordChange(BaseModel):
    model_config = ConfigDict(extra='forbid')

    currentPassword: str = Field(min_length=1)
    newPassword: str = Field(min_length=6, max_length=72)


class PasswordReset(BaseModel):
    model_config = ConfigDict(extra='forbid')

    newPassword: str = Field(min_length=6, max_length=72)


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
    avgChillerLoadRate: float = 0      # 全年冷机平均负荷率（%）= 总供冷量 ÷ Σ在线冷机容量
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
    caliberVersion: str = 'v2'
    # ===== 选型尺度（D3/D4）=====
    capacityFactor: Optional[float] = None   # 冷机容量放大系数
    peakLoad: Optional[float] = None         # 建筑负荷最大值 kW
    installedCapacity: Optional[float] = None  # 总装机容量 kW
    designMargin: Optional[float] = None     # 设计裕度 = 总装机 ÷ 峰值负荷
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