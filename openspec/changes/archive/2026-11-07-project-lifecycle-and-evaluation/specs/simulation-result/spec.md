# Spec Delta

## ADDED Requirements

### Requirement: 全年冷机平均负荷率

结果汇总 SHALL 包含 `avgChillerLoadRate`（百分比），定义为 Σ逐时冷源站供冷量 ÷ Σ(该小时在线冷机额定制冷量 × 1h) × 100%。该指标 SHALL 排除停机小时，且 SHALL 随 `GET /api/simulate/results/{task_id}` 返回。

#### Scenario: 有冷机在线
- **WHEN** 仿真完成且存在冷机在线小时
- **THEN** `summary.avgChillerLoadRate` SHALL 等于按上述公式计算的值，范围 0–100

#### Scenario: 全年无冷机在线
- **WHEN** 仿真期间冷机始终未投运
- **THEN** `summary.avgChillerLoadRate` SHALL 为 0，而不是缺失或无穷大

#### Scenario: 结果接口返回
- **WHEN** 调用 `GET /api/simulate/results/{task_id}`
- **THEN** 响应 `summary` 中 SHALL 包含 `avgChillerLoadRate`，且与结果快照中的值一致

#### Scenario: 旧结果缺少字段
- **WHEN** 读取本次改动前生成、未包含该字段的结果
- **THEN** 消费方 SHALL 将其视为缺失并按"旧结果"处理，不得按 0 分正常参与评价
