from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum

# ===== 枚举类型 =====
class SystemType(str, Enum):
    VAV = "vav"
    CAV = "cav"
    FCU = "fcu"
    VRV = "vrv"

class OperationSchedule(str, Enum):
    CONTINUOUS = "continuous"
    INTERMITTENT = "intermittent"
    CUSTOM = "custom"

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

# ===== 请求模型 =====
class SimulationConfig(BaseModel):
    systemType: SystemType
    operationSchedule: OperationSchedule
    startTime: Optional[str] = "08:00"
    endTime: Optional[str] = "18:00"
    coolingSetpoint: float = Field(ge=20, le=28, default=26)
    heatingSetpoint: float = Field(ge=16, le=24, default=20)
    occupancyDensity: float = Field(ge=0.05, le=0.5, default=0.1)
    lightingPowerDensity: float = Field(ge=5, le=20, default=10)
    equipmentPowerDensity: float = Field(ge=5, le=50, default=15)

class StartSimulationRequest(BaseModel):
    projectName: str = Field(min_length=1, max_length=100)
    buildingType: BuildingType
    area: float = Field(ge=100, le=100000)
    config: SimulationConfig
    data: Dict[str, Any]  # 包含 headers 和 rows

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

# ===== 响应模型 =====
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

# ===== WebSocket 消息 =====
class WSProgressMessage(BaseModel):
    type: str = "progress"
    data: Dict[str, Any]

class WSCompletedMessage(BaseModel):
    type: str = "completed"
    summary: SimulationSummary

class WSFailedMessage(BaseModel):
    type: str = "failed"
    error: str