# Spec Delta

## MODIFIED Requirements

### Requirement: 运行统计

结果 SHALL 给出冷机逐时负荷率的分布统计，以及各类设备的累计投运时长；负荷率分布 SHALL 随结果接口一并返回，供下游直接消费。

#### Scenario: 负荷率分布
- **WHEN** 仿真完成
- **THEN** 结果 SHALL 给出按负荷率区间划分的逐时计数，区间总计数之和 SHALL 等于投运小时数

#### Scenario: 负荷率分布随接口返回
- **WHEN** 调用 `GET /api/simulate/results/{task_id}`
- **THEN** 响应 SHALL 在 `load_rate_histogram` 字段中给出该分布，长度恒为 10，第 i 个元素表示冷机负荷率落在 `[i/10, (i+1)/10)` 区间的逐时计数，最后一个区间包含上限 1.0

#### Scenario: 无投运时的分布表达
- **WHEN** 整个仿真周期内冷机均未投运
- **THEN** `load_rate_histogram` SHALL 返回 10 个 0，而不得缺失该字段

#### Scenario: 投运时长统计
- **WHEN** 仿真完成
- **THEN** 结果 SHALL 给出每类冷机的累计投运小时数，且各类累计投运小时数之和 SHALL 大于或等于总计算小时数除以最小同时投运台数
