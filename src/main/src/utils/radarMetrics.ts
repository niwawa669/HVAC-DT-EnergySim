/**
 * 雷达图五维评价：把不同量纲的指标折算为 0–100 分，位置越靠外表示越好。
 *
 * 评价基准（冷源站口径）说明：
 * - EERa：GB 50189-2015《公共建筑节能设计标准》冷源系统能效系数限值（3.4~4.0），
 *   结合 GB 55015-2021《建筑节能与可再生能源利用通用规范》与 GB 19577-2024
 *   《热泵和冷水机组能效限定值及能效等级》的冷机 IPLV 能效等级；
 * - 单位面积耗电量：GB/T 51161-2016《民用建筑能耗标准》办公建筑非供暖能耗
 *   约束值 70、引导值 55 kWh/(m²·a)，按冷源站约占 35% 折算为冷源站口径；
 * - 单位面积碳排放：GB/T 51366-2019《建筑碳排放计算标准》核算口径，
 *   并参考地方低碳建筑运行碳排放强度限值，按冷源站占比 35% 折算；
 * - 全年冷机平均负荷率、单位面积供冷量：国标未给强制限值，采用运行合理性/常规区间参考。
 *
 * 折算系数与分档阈值集中在本文件，便于后续按新标准调整；调整后雷达图与
 * 下方评价表会同步变化——分数按"当前基准"折算，历史结果的原始数值不变，
 * 但分数与等级会随阈值更新而漂移（见 design.md D5）。
 *
 * 缺少原始指标的维度（改造前的结果没有 avgChillerLoadRate）标记为 available=false：
 * 不参与雷达绘制、等级显示"缺失"，不得按 0 分计入评价（simulation-result 契约）。
 */

export type MetricLevel = '优秀' | '良好' | '达标' | '待改进' | '缺失'

export interface RadarMetric {
  key: string
  name: string
  unit: string
  /** 原始计算值 */
  value: number
  /** 带单位的展示值 */
  display: string
  /** 0–100，越靠外越好 */
  score: number
  level: MetricLevel
  /** 当前值相对基准的判定说明 */
  benchmark: string
  /** 基准依据 */
  source: string
  /** 原始指标是否存在；false 表示旧结果缺字段，不参与评价 */
  available: boolean
}

const COOLING_SHARE = 0.35 // 冷源站电耗/碳排放占建筑总量的大致比例（用于把国标建筑口径折算到冷源站口径）

function num(value: unknown): number {
  const n = Number(value)
  return Number.isFinite(n) ? n : 0
}

const clamp = (value: number, min = 0, max = 100) => Math.min(max, Math.max(min, value))

/** 分段线性打分：points 按“原始值”升序，返回对应的分数。 */
function interpolate(value: number, points: Array<[number, number]>): number {
  if (!points.length) return 0
  const sorted = [...points].sort((a, b) => a[0] - b[0])
  if (value <= sorted[0][0]) return clamp(sorted[0][1])
  for (let i = 1; i < sorted.length; i++) {
    const [x1, y1] = sorted[i - 1]
    const [x2, y2] = sorted[i]
    if (value <= x2) {
      const ratio = x2 === x1 ? 0 : (value - x1) / (x2 - x1)
      return clamp(y1 + (y2 - y1) * ratio)
    }
  }
  return clamp(sorted[sorted.length - 1][1])
}

function levelOf(score: number): MetricLevel {
  if (score >= 85) return '优秀'
  if (score >= 70) return '良好'
  if (score >= 55) return '达标'
  return '待改进'
}

function metric(
  key: string,
  name: string,
  unit: string,
  value: number,
  display: string,
  score: number,
  benchmark: string,
  source: string,
  available = true,
): RadarMetric {
  const safeScore = clamp(Math.round(score))
  return {
    key, name, unit, value, display,
    score: available ? safeScore : 0,
    level: available ? levelOf(safeScore) : '缺失',
    benchmark, source, available,
  }
}

export function buildRadarMetrics(
  summary: Record<string, any>,
  meta: Record<string, any>,
): RadarMetric[] {
  const totalQ = num(summary?.totalQStation)
  const totalEnergy = num(summary?.totalEnergy)
  const area = num(summary?.area) || num(meta?.area)
  const carbon = num(summary?.carbonEmission)

  // 1. 冷源站综合平均能效 EERa
  const eera = num(summary?.systemEER) || (totalEnergy > 0 ? totalQ / totalEnergy : 0)

  // 2. 全年冷机平均负荷率 = Σ逐时供冷量 ÷ Σ(该小时在线冷机额定制冷量 × 1h) × 100%
  //    逐时在线容量由后端随结果输出（avgChillerLoadRate）；旧结果没有该字段。
  const rawChillerLoadRate = summary?.avgChillerLoadRate
  const hasChillerLoadRate =
    rawChillerLoadRate !== null &&
    rawChillerLoadRate !== undefined &&
    Number.isFinite(Number(rawChillerLoadRate))
  const chillerLoadRate = hasChillerLoadRate ? num(rawChillerLoadRate) : 0

  // 3~5. 单位面积指标
  const unitCooling = area > 0 ? totalQ / area : 0
  const unitEnergy = area > 0 ? totalEnergy / area : 0
  const unitCarbon = area > 0 ? carbon / area : 0

  // ===== 分档阈值（0–100 分）=====
  // EERa：4.0 为大型冷源系统达标线（GB 50189-2015），4.5 良好，5.0 优秀
  const eeraScore = interpolate(eera, [
    [2.5, 0],
    [3.4, 40],
    [4.0, 60],
    [4.5, 80],
    [5.0, 100],
  ])

  // 全年冷机平均负荷率：40%~70% 为合理区间（在线冷机容量加权，不是按 8760h 的容量因子）
  const loadRateScore = hasChillerLoadRate
    ? interpolate(chillerLoadRate, [
        [0, 0],
        [20, 25],
        [40, 100],
        [70, 100],
        [85, 45],
        [95, 0],
      ])
    : 0

  // 单位面积供冷量：办公建筑常规区间（非强制限值）
  const unitCoolingScore = interpolate(unitCooling, [
    [0, 0],
    [25, 45],
    [40, 100],
    [70, 100],
    [95, 45],
    [120, 0],
  ])

  // 单位面积耗电量：约束值 70 × 35% ≈ 24.5，引导值 55 × 35% ≈ 19
  const unitEnergyScore = interpolate(unitEnergy, [
    [19, 100],
    [24.5, 60],
    [32, 45],
    [45, 15],
    [60, 0],
  ])

  // 单位面积碳排放：地方低碳限值按 35% 折算（约 14），引导水平约 8.75
  const unitCarbonScore = interpolate(unitCarbon, [
    [8.75, 100],
    [14, 60],
    [20, 40],
    [30, 10],
    [40, 0],
  ])

  return [
    metric(
      'eera',
      '综合平均能效 EERa',
      '',
      eera,
      eera.toFixed(2),
      eeraScore,
      '≥4.0 达标 / ≥4.5 良好 / ≥5.0 优秀',
      'GB 50189-2015 冷源系统能效系数；GB 55015-2021；GB 19577-2024 冷机 IPLV',
    ),
    metric(
      'loadRate',
      '全年冷机平均负荷率',
      '%',
      chillerLoadRate,
      hasChillerLoadRate ? `${chillerLoadRate.toFixed(1)} %` : '—（旧结果）',
      loadRateScore,
      hasChillerLoadRate
        ? '40%~70% 为合理区间（在线冷机容量加权）'
        : '旧结果缺少逐时在线冷机容量，请重新仿真',
      '总供冷量 ÷ Σ(逐时在线冷机额定制冷量 × 1h)；GB 50189-2015 部分负荷性能要求（运行合理性参考）',
      hasChillerLoadRate,
    ),
    metric(
      'unitCooling',
      '单位面积供冷量',
      'kWh/m²·a',
      unitCooling,
      `${unitCooling.toFixed(1)} kWh/m²·a`,
      unitCoolingScore,
      '40~70 kWh/m²·a 为常规区间',
      'GB/T 51161-2016 能耗指标口径 + 办公建筑常规区间（非强制限值）',
    ),
    metric(
      'unitEnergy',
      '单位面积耗电量',
      'kWh/m²·a',
      unitEnergy,
      `${unitEnergy.toFixed(1)} kWh/m²·a`,
      unitEnergyScore,
      `≤24.5 达标 / ≤19 优秀（按冷源占比 ${Math.round(COOLING_SHARE * 100)}% 折算）`,
      'GB/T 51161-2016 办公建筑非供暖能耗约束值 70 / 引导值 55 kWh/(m²·a)',
    ),
    metric(
      'unitCarbon',
      '单位面积碳排放',
      'kgCO₂/m²·a',
      unitCarbon,
      `${unitCarbon.toFixed(2)} kgCO₂/m²·a`,
      unitCarbonScore,
      `≤14 达标 / ≤8.75 优秀（按冷源占比 ${Math.round(COOLING_SHARE * 100)}% 折算）`,
      'GB/T 51366-2019 核算口径 + 地方低碳建筑碳排放限值',
    ),
  ]
}
