"""报告数据组装与前置校验。

设计依据：openspec/changes/report-generation/design.md 的 D4。

本模块只做两件事：
1. 把仿真结果的七区块映射为报告 7 章所需的结构化视图模型（build_report）；
2. 在生成前校验必要字段与参数快照的一致性（validate_result / validate_parameters）。

不做任何结果之外的统计——报告中的每个数值都必须能在结果 JSON 中定位到来源键（见 FIELD_SOURCES）。
"""
from __future__ import annotations

import re as _re
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Tuple

REPORT_VERSION = "v1"

# ===== 展示层格式化（任务反馈：中文标签 / 时间格式 / 两位小数）=====
_BUILDING_TYPE_LABELS = {
    "office": "办公楼",
    "commercial": "商业建筑",
    "residential": "住宅建筑",
    "hospital": "医院建筑",
    "industrial": "工业建筑",
}

_CARBON_LEVEL_LABELS = {
    "provincial": "省级",
    "regional": "区域",
    "national": "全国",
    "fallback": "兜底值",
}

_ISO_RE = _re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?(\.\d+)?(Z|[+-]\d{2}:?\d{2})?$")


def fmt_time(value: Any) -> str:
    """ISO 时间 -> `YYYY-MM-DD HH:MM:SS`（去掉 T、小数点秒与时区）。"""
    text = "" if value is None else str(value)
    if not _ISO_RE.match(text):
        return text
    text = text.replace("T", " ")
    text = text.split(".")[0].rstrip("Z")
    if len(text) == 16:  # YYYY-MM-DD HH:MM
        text += ":00"
    return text


def fmt_num(value: Any) -> str:
    """浮点保留两位小数（四舍五入）。

    例外：|value| < 1 的非零值（换算系数、排放因子、含湿量等）按有效小数保留，
    否则会被抹成 0.00 而失去意义。整数原样输出。
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, int):
        return str(value)
    try:
        dec = Decimal(str(value))
    except Exception:
        return str(value)
    if dec == 0:
        return "0.00"
    if abs(dec) < 1:
        q = dec.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP).normalize()
        return format(q, "f")
    return str(dec.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def fmt_display(value: Any) -> str:
    """通用展示：时间走 fmt_time，数字走 fmt_num，其余原样。"""
    if isinstance(value, str):
        return fmt_time(value)
    return fmt_num(value)


def label_building_type(value: Any) -> str:
    code = getattr(value, "value", value)
    code = str(code or "").strip()
    # 兼容枚举被 str() 之后的形式，如 "BuildingType.OFFICE"
    if "." in code:
        code = code.rsplit(".", 1)[-1]
    return _BUILDING_TYPE_LABELS.get(code.lower(), code)


def label_carbon_level(value: Any) -> str:
    code = getattr(value, "value", value)
    code = str(code or "").strip()
    return _CARBON_LEVEL_LABELS.get(code.lower(), code)


class ReportValidationError(ValueError):
    """前置校验失败：missing 列出缺失或不合规的字段路径。"""

    def __init__(self, missing: List[str], reason: str = "缺失或不可用"):
        self.missing = list(missing)
        self.reason = reason
        super().__init__(f"报告生成前置校验失败（{reason}）：" + "、".join(self.missing))


# ===== 字段溯源表 =====
# (视图键, 结果路径, 中文标签, 单位)。视图模型的每个数值都来自这里，
# 因此"报告数据只取自结果契约"是可被程序检查的，而不是口头约定。
FIELD_SOURCES: Dict[str, List[Tuple[str, str, str, str]]] = {
    "1": [
        ("projectName", "meta.projectName", "项目名称", ""),
        ("buildingType", "meta.buildingType", "建筑类型", ""),
        ("area", "meta.area", "空调面积", "m²"),
        ("startTime", "meta.startTime", "仿真起始", ""),
        ("endTime", "meta.endTime", "仿真结束", ""),
        ("totalHours", "meta.totalHours", "计算小时数", "h"),
    ],
    "2": [
        ("fileName", "meta.fileName", "数据文件", ""),
        ("totalRows", "meta.totalRows", "数据行数", "行"),
        ("confirmedRange", "meta.confirmedRange", "确认时间范围", ""),
        ("correctedOutliers", "meta.correctedOutliers", "修正异常值", "个"),
        ("tDryRange", "meta.tDryMin", "干球温度范围", "℃"),
        ("humidRange", "meta.humidMin", "含湿量范围", "kg/kg"),
        ("capacityFactor", "meta.capacityFactor", "冷机容量放大系数", ""),
        ("caliberVersion", "meta.caliberVersion", "口径版本", ""),
    ],
    "4": [
        ("totalCoolingLoad", "summary.totalCoolingLoad", "建筑总冷负荷", "kWh"),
        ("totalQStation", "summary.totalQStation", "冷源站总供冷量", "kWh"),
        ("totalEnergy", "summary.totalEnergy", "冷源站总耗电量", "kWh"),
        ("peakCoolingLoad", "summary.peakCoolingLoad", "尖峰冷负荷", "kW"),
        ("eui", "summary.eui", "单位面积耗电量", "kWh/m²"),
        ("avgCop", "summary.avgCop", "冷机平均 COP", ""),
        ("systemEER", "summary.systemEER", "冷源站综合能效", ""),
        ("carbonEmission", "summary.carbonEmission", "碳排放量", "kgCO₂"),
    ],
}

# 生成报告绝对必需的字段：(结果路径, 中文名)
REQUIRED_FIELDS: List[Tuple[str, str]] = [
    ("meta.projectName", "项目名称"),
    ("meta.area", "空调面积"),
    ("meta.carbonFactor.value", "碳排放因子"),
    ("meta.caliberVersion", "口径版本"),
    ("summary", "汇总指标"),
    ("breakdown", "分项能耗"),
]

_BREAKDOWN_KEYS = ("chiller", "pump_chw", "pump_cw", "tower")
_BREAKDOWN_LABELS = {"chiller": "冷机", "pump_chw": "冷冻泵", "pump_cw": "冷却泵", "tower": "冷却塔"}


# ===== 参数中文标签（第 3 章展示用，键名保持可追溯）=====
# 报告要求「使用简体中文表述、每个指标附带明确单位」；参数快照仍以原始键名保存，
# 这里只负责展示名。新增参数时必须同步本表，否则第 3 章会退化显示英文键（测试会报出）。
PARAM_LABELS: Dict[str, Tuple[str, str]] = {
    # 建筑与尺度
    "load_building_r": ("建筑设计峰值负荷", "kW"),
    "capacity_factor": ("冷机容量放大系数", ""),
    # 冷机
    "Qr_chiller_BCH": ("大机额定制冷量", "kW"),
    "n_design_BCH": ("大机台数", "台"),
    "COP_chiller_BCH": ("大机 COP（标称）", ""),
    "Qr_chiller_SCH": ("小机额定制冷量", "kW"),
    "n_design_SCH": ("小机台数", "台"),
    "COP_chiller_SCH": ("小机 COP（标称）", ""),
    "ts_chw_design": ("冷冻水供水温度设计值", "℃"),
    "tr_chw_design": ("冷冻水回水温度设计值", "℃"),
    "tr_cw_design": ("冷却水回水温度设计值", "℃"),
    "ts_cw_design": ("冷却水供水温度设计值", "℃"),
    # 冷冻泵
    "Gr_pump_chw_BCH": ("大机冷冻泵设计流量", "L/s"),
    "Hr_pump_chw_BCH": ("大机冷冻泵设计扬程", "mH₂O"),
    "n_pump_chw_BCH": ("大机冷冻泵台数", "台"),
    "Gr_pump_chw_SCH": ("小机冷冻泵设计流量", "L/s"),
    "Hr_pump_chw_SCH": ("小机冷冻泵设计扬程", "mH₂O"),
    "n_pump_chw_SCH": ("小机冷冻泵台数", "台"),
    # 冷却泵
    "Gr_pump_cw_BCH": ("大机冷却泵设计流量", "L/s"),
    "Hr_pump_cw_BCH": ("大机冷却泵设计扬程", "mH₂O"),
    "n_pump_cw_BCH": ("大机冷却泵台数", "台"),
    "Gr_pump_cw_SCH": ("小机冷却泵设计流量", "L/s"),
    "Hr_pump_cw_SCH": ("小机冷却泵设计扬程", "mH₂O"),
    "n_pump_cw_SCH": ("小机冷却泵台数", "台"),
    # 冷却塔
    "Gr_tower_BCH": ("大机冷却塔设计流量", "L/s"),
    "Pr_tower_BCH": ("大机冷却塔设计功率（标称）", "kW"),
    "Hs_tower_BCH": ("大机冷却塔设计压降", "mH₂O"),
    "n_tower_BCH": ("大机冷却塔台数", "台"),
    "Gr_tower_SCH": ("小机冷却塔设计流量", "L/s"),
    "Pr_tower_SCH": ("小机冷却塔设计功率（标称）", "kW"),
    "Hs_tower_SCH": ("小机冷却塔设计压降", "mH₂O"),
    "n_tower_SCH": ("小机冷却塔台数", "台"),
    # 管道压降
    "Hr_pt": ("冷冻供回水总管扬程", "mH₂O"),
    "Hr_chiller_chw_BCH": ("大机冷机冷冻水侧设计压降", "mH₂O"),
    "Hr_chiller_cw_BCH": ("大机冷机冷却水侧设计压降", "mH₂O"),
    "Hr_chiller_chw_SCH": ("小机冷机冷冻水侧设计压降", "mH₂O"),
    "Hr_chiller_cw_SCH": ("小机冷机冷却水侧设计压降", "mH₂O"),
    # 群控与设计工况
    "ta_dry_r": ("室外干球温度设计值", "℃"),
    "ta_wet_r": ("室外湿球温度设计值", "℃"),
    "ts_chw_set": ("冷冻水供水温度设定值", "℃"),
    "delta_t_chw": ("冷冻水供回水温差", "℃"),
    "delta_t_cw": ("冷却水供回水温差", "℃"),
    "tr_cw_min": ("冷却水回水温度最小值", "℃"),
    "approach_set": ("冷却塔逼近度", "℃"),
    "load_up": ("加机负荷率", ""),
    "load_min": ("冷机最小负荷率", ""),
    "freq_pump_max": ("水泵最高频率", "Hz"),
    "freq_pump_min": ("水泵最低频率", "Hz"),
    "freq_tower_max": ("冷却塔风机最高频率", "Hz"),
    "freq_tower_min": ("冷却塔风机最低频率", "Hz"),
    # 序列与口径
    "Qr_list": ("加机优先级（额定冷量序列）", "kW"),
    "n_design_list": ("加机优先级（台数序列）", "台"),
    "carbon_year": ("碳排因子核算年度", ""),
    "carbon_province": ("碳排因子适用省份", ""),
    "applicable_range": ("模型适用范围", ""),
}


def _fmt_sequence(name: str, value: Any) -> Optional[str]:
    """序列类参数的可读呈现（D5）：不出现裸数组。"""
    if not isinstance(value, list) or not value:
        return None
    if name == 'Qr_list' and len(value) >= 2:
        return f"小机 {fmt_display(value[0])} kW → 大机 {fmt_display(value[1])} kW"
    if name == 'n_design_list':
        return " → ".join(f"{int(v)} 台" for v in value)
    return " → ".join(fmt_display(v) for v in value)


def param_label(name: str) -> Tuple[str, str]:
    """返回参数的（中文名, 单位）；未登记时回退为键名本身。"""
    return PARAM_LABELS.get(name, (name, ""))


def resolve(source: Dict[str, Any], path: str) -> Any:
    """按点号路径取值，缺失返回 None。"""
    cur: Any = source
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _is_blank(value: Any) -> bool:
    return value is None or value == "" or (isinstance(value, list) and len(value) == 0)


def validate_result(result: Dict[str, Any]) -> None:
    """生成前置校验（D4 / 任务 2.2）：缺关键字段即失败并指名字段。"""
    missing = [label for path, label in REQUIRED_FIELDS if _is_blank(resolve(result, path))]
    breakdown = resolve(result, "breakdown") or {}
    if isinstance(breakdown, dict):
        missing += [f"分项能耗.{_BREAKDOWN_LABELS[k]}" for k in _BREAKDOWN_KEYS if breakdown.get(k) is None]
    if missing:
        raise ReportValidationError(missing)


def _as_number(value: Any) -> Any:
    try:
        return float(value)
    except (TypeError, ValueError):
        return value


def validate_parameters(view: Dict[str, Any], result: Dict[str, Any]) -> None:
    """参数快照一致性校验（任务 2.3）：报告中出现的参数必须与结果快照逐项相等。"""
    snapshot = resolve(result, "meta.parameters") or {}
    if not isinstance(snapshot, dict) or not snapshot:
        raise ReportValidationError(["meta.parameters"], reason="参数快照缺失")

    report_params = (view.get("chapters", {}).get("3", {}) or {}).get("parameters") or {}
    bad: List[str] = []
    for name, value in report_params.items():
        if name not in snapshot:
            bad.append(name)
        elif _as_number(value) != _as_number(snapshot[name]):
            bad.append(name)
    for name in (resolve(result, "meta.displayOnly") or []):
        if name not in snapshot:
            bad.append(name)
    if bad:
        raise ReportValidationError(sorted(set(bad)), reason="与结果中的参数快照不一致")


def _metric(key: str, label: str, unit: str, value: Any) -> Dict[str, Any]:
    return {"key": key, "label": label, "unit": unit, "value": value}


def _chapter_results(result: Dict[str, Any]) -> Dict[str, Any]:
    chapters: Dict[str, Any] = {}

    chapters["1"] = {
        "title": "封面与方案概览",
        "items": [_metric(k, label, unit, resolve(result, path))
                  for k, path, label, unit in FIELD_SOURCES["1"]],
    }

    items = []
    for k, path, label, unit in FIELD_SOURCES["2"]:
        if k == "tDryRange":
            items.append(_metric(k, label, unit, [resolve(result, "meta.tDryMin"),
                                                  resolve(result, "meta.tDryMax")]))
        elif k == "humidRange":
            items.append(_metric(k, label, unit, [resolve(result, "meta.humidMin"),
                                                  resolve(result, "meta.humidMax")]))
        else:
            items.append(_metric(k, label, unit, resolve(result, path)))
    chapters["2"] = {"title": "输入数据与数据质量", "items": items}

    snapshot = resolve(result, "meta.parameters") or {}
    chapters["3"] = {
        "title": "设备选型与群控参数",
        "parameters": dict(snapshot),
        "displayOnly": list(resolve(result, "meta.displayOnly") or []),
        "deviations": resolve(result, "meta.displayOnlyDeviations") or {},
        # 选型尺度（D3/D4）：派生只读，报告需如实回显
        "caliber": {
            "designMargin": resolve(result, "meta.designMargin"),
            "capacityFactor": resolve(result, "meta.capacityFactor"),
            "installedCapacity": resolve(result, "meta.installedCapacity"),
            "peakLoad": resolve(result, "meta.peakLoad"),
        },
    }

    chapters["4"] = {
        "title": "全年能耗与能效结果",
        "metrics": [_metric(k, label, unit, resolve(result, path))
                    for k, path, label, unit in FIELD_SOURCES["4"]],
        "breakdown": {k: (resolve(result, "breakdown") or {}).get(k, 0) for k in _BREAKDOWN_KEYS},
        "breakdownLabels": dict(_BREAKDOWN_LABELS),
    }

    chapters["5"] = {
        "title": "时间维度分析",
        "monthly": resolve(result, "monthly") or [],
        "weekly": resolve(result, "weekly") or [],
    }

    chapters["6"] = {
        "title": "运行工况分析",
        "operatingStats": resolve(result, "operating_stats") or {},
        "loadRateHistogram": resolve(result, "load_rate_histogram") or [0] * 10,
        "peak": resolve(result, "peak_context") or {},
    }

    chapters["7"] = {
        "title": "结论与口径说明",
        "supplyGap": {
            "totalUnmet": resolve(result, "summary.totalUnmet") or 0,
            "unmetHours": resolve(result, "summary.unmetHours") or 0,
            "unservedWhenOff": resolve(result, "summary.totalUnservedOff") or 0,
        },
        "unmetHoursDetail": resolve(result, "unmet_hours_detail") or [],
        "carbon": resolve(result, "meta.carbonFactor") or {},
        "extrapolation": resolve(result, "meta.extrapolation") or {},
        "applicableRange": resolve(result, "meta.applicableRange") or {},
        "caliber": {
            "version": resolve(result, "meta.caliberVersion"),
            "capacityFactor": resolve(result, "meta.capacityFactor"),
        },
    }
    return chapters


def build_report(result: Dict[str, Any], generated_at: str = "") -> Dict[str, Any]:
    """把仿真结果映射为报告视图模型（任务 2.1）。调用前须先通过 validate_result。"""
    chapters = _chapter_results(result)
    return {
        "reportVersion": REPORT_VERSION,
        "generatedAt": generated_at,
        "taskId": resolve(result, "taskId"),
        "caliberVersion": resolve(result, "meta.caliberVersion"),
        "chapters": chapters,
        "chapterOrder": ["1", "2", "3", "4", "5", "6", "7"],
        "chapterTitles": {k: chapters[k]["title"] for k in chapters},
    }


def traceability(result: Dict[str, Any]) -> Dict[str, Any]:
    """自检：FIELD_SOURCES 声明的每个字段都能在结果中定位到来源键且非空。"""
    checked, unresolved = 0, []
    for chapter_key, rows in FIELD_SOURCES.items():
        for key, path, _label, _unit in rows:
            checked += 1
            if _is_blank(resolve(result, path)):
                unresolved.append(f"{chapter_key}.{key}<-{path}")
    return {"checked": checked, "unresolved": unresolved}

# ===== 服务端 SVG 图表（D3）=====
# 只用 <rect>/<line>/<polyline>/<circle>/<text>，不含 <script>、不引用外部资源，
# 因此写入 HTML 后字节稳定、打印时无需执行 JS。

SVG_W, SVG_H = 680, 240
PAD_L, PAD_R, PAD_T, PAD_B = 52, 18, 18, 38
FONT = "'Microsoft YaHei','PingFang SC','SimSun',sans-serif"


def _num(value: Any, default: float = 0.0) -> float:
    """把任意输入转成有限浮点数；NaN/Infinity/非数字一律回落，避免画布出现非法坐标。"""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    if v != v or v in (float("inf"), float("-inf")):
        return default
    return v


def _fmt(value: float, nd: int = 2) -> str:
    txt = f"{value:.{nd}f}"
    return txt.rstrip("0").rstrip(".") if "." in txt else txt


def _plot_box() -> Tuple[float, float, float, float]:
    return PAD_L, PAD_T, SVG_W - PAD_L - PAD_R, SVG_H - PAD_T - PAD_B


def _svg_open(title: str) -> List[str]:
    return [
        # 不带 xmlns：这些 SVG 只作为 HTML5 内联元素存在，而 HTML5 内联 svg 自动属于 SVG 命名空间。
        # 去掉后整份报告的 HTML 字面量中不含任何 http(s) 字符串，可被 grep 直接断言"无外链"。
        f'<svg width="{SVG_W}" height="{SVG_H}" '
        f'viewBox="0 0 {SVG_W} {SVG_H}" role="img" aria-label="{title}">',
        f'<text x="{PAD_L}" y="12" font-family="{FONT}" font-size="12" fill="#303133">{title}</text>',
    ]


def _empty_state(title: str, reason: str = "无数据") -> str:
    lines = _svg_open(title)
    cx, cy = SVG_W / 2, SVG_H / 2
    lines.append(f'<rect x="{PAD_L}" y="{PAD_T}" width="{SVG_W - PAD_L - PAD_R}" '
                 f'height="{SVG_H - PAD_T - PAD_B}" fill="none" stroke="#dcdfe6" stroke-dasharray="4 4"/>')
    lines.append(f'<text x="{cx}" y="{cy}" text-anchor="middle" font-family="{FONT}" '
                 f'font-size="13" fill="#909399">{reason}</text>')
    lines.append("</svg>")
    return "".join(lines)


def _axis(x0: float, y0: float, w: float, h: float, ymax: float, ylabel: str) -> List[str]:
    return [
        f'<line x1="{x0}" y1="{y0 + h}" x2="{x0 + w}" y2="{y0 + h}" stroke="#c0c4cc"/>',
        f'<line x1="{x0}" y1="{y0}" x2="{x0}" y2="{y0 + h}" stroke="#c0c4cc"/>',
        f'<text x="{x0 - 6}" y="{y0 + 4}" text-anchor="end" font-family="{FONT}" '
        f'font-size="10" fill="#909399">{_fmt(ymax, 1)}</text>',
        f'<text x="{x0 - 6}" y="{y0 + h}" text-anchor="end" font-family="{FONT}" '
        f'font-size="10" fill="#909399">0</text>',
        f'<text x="{x0 - 34}" y="{y0 - 6}" font-family="{FONT}" font-size="10" '
        f'fill="#909399">{ylabel}</text>',
    ]


def svg_monthly_energy_bar(monthly: List[Dict[str, Any]], title: str = "月度能耗（kWh）") -> str:
    """月度能耗柱状图（任务 3.1）。柱数恒等于 monthly 条数。"""
    if not monthly:
        return _empty_state(title, "无月度数据")
    values = [_num(m.get("totalEnergyConsumption")) for m in monthly]
    ymax = max(values) if values else 0.0
    ymax = ymax * 1.15 if ymax > 0 else 1.0

    x0, y0, w, h = _plot_box()
    n = len(values)
    slot = w / n
    bar_w = max(2.0, slot * 0.62)

    lines = _svg_open(title)
    lines += _axis(x0, y0, w, h, ymax, "kWh")
    for i, v in enumerate(values):
        bh = (v / ymax) * h if ymax > 0 else 0.0
        bx = x0 + slot * i + (slot - bar_w) / 2
        by = y0 + h - bh
        lines.append(f'<rect class="bar" x="{bx:.2f}" y="{by:.2f}" width="{bar_w:.2f}" '
                     f'height="{max(bh, 0):.2f}" fill="#409eff"/>')
        label = str((monthly[i].get("month") or "")[-2:] or i + 1)
        lines.append(f'<text x="{bx + bar_w / 2:.2f}" y="{y0 + h + 14}" text-anchor="middle" '
                     f'font-family="{FONT}" font-size="9" fill="#606266">{label}</text>')
    lines.append(f'<text x="{x0 + w}" y="{SVG_H - 6}" text-anchor="end" font-family="{FONT}" '
                 f'font-size="9" fill="#909399">横轴：月份</text>')
    lines.append("</svg>")
    return "".join(lines)


def svg_monthly_eer_line(monthly: List[Dict[str, Any]], title: str = "月度能效（系统 EER）") -> str:
    """月度能效折线图（任务 3.2）。数据点数恒等于 monthly 条数，缺失值按 0 占位。"""
    if not monthly:
        return _empty_state(title, "无月度数据")
    values = [_num(m.get("systemEER")) for m in monthly]
    ymax = max(values) if values else 0.0
    ymax = ymax * 1.15 if ymax > 0 else 1.0

    x0, y0, w, h = _plot_box()
    n = len(values)
    step = (w / (n - 1)) if n > 1 else 0.0

    pts = []
    for i, v in enumerate(values):
        px = x0 + (step * i if n > 1 else w / 2)
        py = y0 + h - (v / ymax) * h
        pts.append(f"{px:.2f},{py:.2f}")

    lines = _svg_open(title)
    lines += _axis(x0, y0, w, h, ymax, "EER")
    lines.append(f'<polyline class="line" points="{" ".join(pts)}" fill="none" '
                 f'stroke="#67c23a" stroke-width="1.6"/>')
    for i, p in enumerate(pts):
        cx_, cy_ = p.split(",")
        lines.append(f'<circle cx="{cx_}" cy="{cy_}" r="2.4" fill="#67c23a"/>')
        label = str((monthly[i].get("month") or "")[-2:] or i + 1)
        lines.append(f'<text x="{cx_}" y="{y0 + h + 14}" text-anchor="middle" '
                     f'font-family="{FONT}" font-size="9" fill="#606266">{label}</text>')
    lines.append(f'<text x="{x0 + w}" y="{SVG_H - 6}" text-anchor="end" font-family="{FONT}" '
                 f'font-size="9" fill="#909399">横轴：月份</text>')
    lines.append("</svg>")
    return "".join(lines)


def breakdown_percentages(breakdown: Dict[str, Any]) -> Dict[str, float]:
    """四分项占比（%），保证合计恰好为 100.0（最后一个非零项吸收舍入余量）。"""
    total = sum(_num(breakdown.get(k)) for k in _BREAKDOWN_KEYS)
    if total <= 0:
        return {k: 0.0 for k in _BREAKDOWN_KEYS}
    raw = {k: _num(breakdown.get(k)) / total * 100.0 for k in _BREAKDOWN_KEYS}
    pct = {k: round(v, 1) for k, v in raw.items()}
    drift = round(100.0 - sum(pct.values()), 1)
    if drift:
        biggest = max(pct, key=lambda k: pct[k])
        pct[biggest] = round(pct[biggest] + drift, 1)
    return pct


def svg_breakdown_stack(breakdown: Dict[str, Any], total_energy: Any = None,
                        title: str = "能耗构成") -> str:
    """能耗构成堆叠条（任务 3.3）。传入 total_energy 时先校验加和守恒。"""
    if total_energy is not None:
        s = sum(_num(breakdown.get(k)) for k in _BREAKDOWN_KEYS)
        if abs(s - _num(total_energy)) > 1e-6:
            raise ReportValidationError(["breakdown"], reason="分项加和与总耗电量不一致")

    colors = {"chiller": "#409eff", "pump_chw": "#67c23a", "pump_cw": "#e6a23c", "tower": "#909399"}
    pct = breakdown_percentages(breakdown)
    total = sum(_num(breakdown.get(k)) for k in _BREAKDOWN_KEYS)
    if total <= 0:
        return _empty_state(title, "无能耗数据")

    x0, y0, w, h = _plot_box()
    bar_y, bar_h = y0 + 18, 34
    lines = _svg_open(title)
    cursor = x0
    for k in _BREAKDOWN_KEYS:
        seg_w = (pct[k] / 100.0) * w
        lines.append(f'<rect class="seg" x="{cursor:.2f}" y="{bar_y}" width="{seg_w:.2f}" '
                     f'height="{bar_h}" fill="{colors[k]}"/>')
        if seg_w > 46:
            lines.append(f'<text x="{cursor + seg_w / 2:.2f}" y="{bar_y + bar_h / 2 + 4}" '
                         f'text-anchor="middle" font-family="{FONT}" font-size="10" '
                         f'fill="#ffffff">{pct[k]:.1f}%</text>')
        cursor += seg_w

    # 图例
    ly = bar_y + bar_h + 24
    for idx, k in enumerate(_BREAKDOWN_KEYS):
        lx = x0 + (idx % 2) * (w / 2)
        if idx == 2:
            ly += 18
        lines.append(f'<rect x="{lx:.2f}" y="{ly - 8}" width="10" height="10" fill="{colors[k]}"/>')
        lines.append(f'<text x="{lx + 15:.2f}" y="{ly}" font-family="{FONT}" font-size="10" '
                     f'fill="#606266">{_BREAKDOWN_LABELS[k]} {_fmt(_num(breakdown.get(k)))} kWh'
                     f'（{pct[k]:.1f}%）</text>')
    lines.append("</svg>")
    return "".join(lines)

# ===== HTML 快照渲染与原子落盘（D1/D2/D5）=====
import json as _json
import os
import shutil
from datetime import datetime, timedelta, timezone

from app.config import settings

# 报告目录由配置决定（D10）；兼容 HVAC_REPORTS_DIR 环境变量（见 settings.reports_dir）
REPORTS_DIR = str(settings.reports_dir)

_CSS = """
@page { size: A4; margin: 16mm 14mm; }
* { box-sizing: border-box; }
body { font-family: 'Microsoft YaHei','PingFang SC','SimSun',sans-serif; color:#303133; font-size:11px; line-height:1.6; margin:0; }
h1 { font-size:20px; margin:0 0 4px; }
h2 { font-size:14px; margin:18px 0 8px; padding-bottom:4px; border-bottom:1px solid #dcdfe6; }
h2 .no { color:#409eff; margin-right:6px; }
h3 { font-size:12px; margin:12px 0 6px; color:#606266; }
.sub { color:#909399; font-size:10px; }
table { width:100%; border-collapse:collapse; margin:6px 0 10px; page-break-inside:auto; }
thead { display:table-header-group; }
tr { page-break-inside:avoid; }
th,td { border:1px solid #dcdfe6; padding:3px 6px; text-align:left; vertical-align:top; }
th { background:#f5f7fa; font-weight:600; }
td.num { text-align:right; }
.chart { margin:8px 0 12px; page-break-inside:avoid; }
.note { background:#f4f4f5; border-left:3px solid #909399; padding:6px 10px; margin:8px 0; }
.warn { background:#fdf6ec; border-left:3px solid #e6a23c; padding:6px 10px; margin:8px 0; }
.cover { page-break-after:always; }
.cover .meta { margin-top:24px; }
"""


def _esc(value: Any) -> str:
    text = "" if value is None else str(value)
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))


def _table(headers: List[str], rows: List[List[Any]], numeric_from: int = 1) -> str:
    head = "".join(f"<th>{_esc(h)}</th>" for h in headers)
    body = []
    for row in rows:
        cells = []
        for idx, cell in enumerate(row):
            cls = ' class="num"' if idx >= numeric_from else ""
            cells.append(f"<td{cls}>{_esc(fmt_display(cell))}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def _disp_item(item: Dict[str, Any]) -> str:
    """条目展示：建筑类型与碳排层级转中文，其余按通用规则。"""
    key = item.get("key")
    value = item.get("value")
    if key == "buildingType":
        return label_building_type(value)
    if isinstance(value, list):  # 区间类，如干球温度范围
        return " ~ ".join(fmt_display(v) for v in value)
    return fmt_display(value)


def _items_table(items: List[Dict[str, Any]]) -> str:
    rows = [[i.get("label"), _disp_item(i), i.get("unit")] for i in items]
    head = "".join(f"<th>{_esc(h)}</th>" for h in ["项目", "取值", "单位"])
    body = "".join(
        "<tr>" + f"<td>{_esc(r[0])}</td>" + f'<td class="num">{_esc(r[1])}</td>' + f"<td>{_esc(r[2])}</td>" + "</tr>"
        for r in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def _value_of(items: List[Dict[str, Any]], key: str) -> Any:
    for it in items:
        if it.get("key") == key:
            return it.get("value")
    return ""


def _chapter(no: str, title: str, body: str) -> str:
    return f'<section data-chapter="{no}"><h2><span class="no">{no}</span>{_esc(title)}</h2>{body}</section>'


def _now_iso() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")


def make_report_id(task_id: str) -> str:
    """report_id = <task 前 8 位>-<生成时间戳>（D6）。"""
    return f"{(task_id or 'unknown')[:8]}-{datetime.now().strftime('%Y%m%d%H%M%S')}"


def render_html(view: Dict[str, Any], result: Dict[str, Any]) -> str:
    """渲染自包含报告 HTML（任务 4.1）：无 <script>、无 http(s)、无外链资源。"""
    ch = view.get("chapters") or {}
    c1, c2, c3 = ch.get("1", {}), ch.get("2", {}), ch.get("3", {})
    c4, c5, c6, c7 = ch.get("4", {}), ch.get("5", {}), ch.get("6", {}), ch.get("7", {})

    cover_items = c1.get("items") or []
    short = "".join(f'<div>{_esc(i.get("label"))}：<b>{_esc(_disp_item(i))}</b> {_esc(i.get("unit"))}</div>'
                    for i in cover_items[1:4])
    ch1 = _chapter("1", c1.get("title", "封面与方案概览"),
                   f'<div class="cover"><h1>{_esc(_value_of(cover_items, "projectName"))}'
                   f' — 全年冷源站能耗仿真报告</h1>'
                   f'<div class="sub">报告版本 {_esc(view.get("reportVersion"))}　生成时间 '
                   f'{_esc(fmt_time(view.get("generatedAt")))}　'
                   f'口径版本 {_esc(view.get("caliberVersion"))}</div>'
                   f'<div class="meta">{short}</div>{_items_table(cover_items)}</div>')

    ch2 = _chapter("2", c2.get("title", "输入数据与数据质量"), _items_table(c2.get("items") or []))

    display_only = set(c3.get("displayOnly") or [])
    deviations = c3.get("deviations") or {}
    rows = []
    for name, value in (c3.get("parameters") or {}).items():
        role = "仅展示" if name in display_only else "参与计算"
        dev = deviations.get(name) or {}
        dev_txt = (f'{fmt_display(dev.get("nominal"))} → {fmt_display(dev.get("model"))}'
                   if dev else "—")
        label, unit = param_label(name)
        # 序列类参数改为可读形式，避免报告里出现裸数组
        shown = _fmt_sequence(name, value) or fmt_display(value)
        rows.append([label, shown, unit, role, dev_txt])
    cal3 = c3.get("caliber") or {}
    scale_rows = [
        ["设计裕度", cal3.get("designMargin"),
         "总装机 ÷ 建筑负荷最大值（派生只读）"],
        ["冷机容量放大系数", cal3.get("capacityFactor"),
         "2112.6 × 该系数 = 实际单机容量（派生只读）"],
        ["总装机容量(kW)", cal3.get("installedCapacity"), "各机型实际容量 × 台数之和"],
        ["建筑负荷最大值(kW)", cal3.get("peakLoad"), "取自本次输入数据"],
    ]
    ch3 = _chapter("3", c3.get("title", "设备选型与群控参数"),
                   _table(["参数", "取值", "单位", "作用", "标称 → 模型"], rows, numeric_from=1)
                   + ('<div class="note">标注为「仅展示」的参数不参与能耗计算，仅用于选型对照与标称值校核。</div>'
                      if display_only else "")
                   + "<h3>选型尺度（派生只读）</h3>"
                   + _table(["项", "取值", "说明"], scale_rows, numeric_from=1)
                   + '<div class="note">设计裕度 = 所有冷机实际额定制冷量之和 ÷ 建筑负荷最大值，'
                     '合理区间 0.9 ~ 1.1；该值由系统计算，不接受手工录入。</div>')

    bd = c4.get("breakdown") or {}
    bd_total = sum(_num(bd.get(k)) for k in _BREAKDOWN_KEYS)
    ch4 = _chapter("4", c4.get("title", "全年能耗与能效结果"),
                   _items_table(c4.get("metrics") or [])
                   + f'<div class="chart">{svg_breakdown_stack(bd, total_energy=bd_total)}</div>')

    monthly = c5.get("monthly") or []
    weekly = c5.get("weekly") or []
    month_rows = [[m.get("month"), m.get("hours"), m.get("totalQStation"),
                   m.get("totalEnergyConsumption"), m.get("systemEER"), m.get("avgChillerCop")] for m in monthly]
    weekly_rows = [[w.get("weekLabel") or w.get("weekNumber"), w.get("weekStart"), w.get("hours"),
                    w.get("totalQStation"), w.get("totalEnergyConsumption"), w.get("avgSystemCop")] for w in weekly]
    ch5 = _chapter("5", c5.get("title", "时间维度分析"),
                   f'<div class="chart">{svg_monthly_energy_bar(monthly)}</div>'
                   f'<div class="chart">{svg_monthly_eer_line(monthly)}</div>'
                   + _table(["月份", "小时数", "供冷量(kWh)", "耗电量(kWh)", "系统能效", "冷机COP"],
                            month_rows, numeric_from=1)
                   + "<h3>逐周明细</h3>"
                   + _table(["周", "起止", "小时数", "供冷量(kWh)", "耗电量(kWh)", "系统能效"],
                            weekly_rows, numeric_from=2))

    hist = c6.get("loadRateHistogram") or [0] * 10
    op = c6.get("operatingStats") or {}
    peak = c6.get("peak") or {}
    ch6 = _chapter("6", c6.get("title", "运行工况分析"),
                   _table(["设备类型", "累计投运小时"], [[k, v] for k, v in op.items()], numeric_from=1)
                   + "<h3>负荷率分布</h3>"
                   + _table(["负荷率区间", "逐时计数"],
                            [[f"{i/10:.1f}–{(i+1)/10:.1f}", v] for i, v in enumerate(hist)], numeric_from=1)
                   + "<h3>尖峰工况</h3>"
                   + _table(["项", "取值"],
                            [["时刻", peak.get("timestamp")], ["冷负荷(kW)", peak.get("load")],
                             ["室外干球温度(℃)", peak.get("temperature")],
                             ["系统能效", peak.get("systemEER")],
                             ["投运台数(SCH/BCH)", f'{peak.get("nSCH")} / {peak.get("nBCH")}'],
                             ["冷机负荷率", peak.get("loadRate")]], numeric_from=1))

    gap = c7.get("supplyGap") or {}
    carbon = c7.get("carbon") or {}
    extrap = c7.get("extrapolation") or {}
    detail = c7.get("unmetHoursDetail") or []
    gap_note = ('<div class="warn">供冷缺口大于 0：装机容量在极端工况下不足以覆盖建筑冷负荷，'
                '缺口明细见下表。</div>' if _num(gap.get("totalUnmet")) > 0
                else '<div class="note">供冷缺口为 0：装机容量在全时段均覆盖建筑冷负荷。</div>')
    extrap_note = ('<div class="warn">存在超出模型适用范围的外推记录：'
                   f'{_esc(extrap.get("hours"))} 小时，占 {_num(extrap.get("ratio")) * 100:.2f}%，'
                   '该部分结果置信度较低。</div>' if _num(extrap.get("hours")) > 0
                   else '<div class="note">无外推记录：全部小时均落在声明的适用范围内'
                        '（该范围由用户声明，非模型真实训练域）。</div>')
    detail_html = ("<h3>缺口发生时刻</h3>" + _table(
        ["时间", "需求(kW)", "实际供冷(kW)", "缺口(kW)", "负荷率", "台数"],
        [[d.get("timestamp"), d.get("demand"), d.get("served"), d.get("unmet"),
          d.get("loadRate"), f'{d.get("nSCH")}/{d.get("nBCH")}'] for d in detail],
        numeric_from=1)) if detail else ""
    ch7 = _chapter("7", c7.get("title", "结论与口径说明"),
                   gap_note
                   + _table(["项", "取值"],
                            [["供冷缺口(kWh)", gap.get("totalUnmet")],
                             ["缺口小时数(h)", gap.get("unmetHours")],
                             ["停机未供冷量(kWh)", gap.get("unservedWhenOff")]], numeric_from=1)
                   + detail_html
                   + "<h3>口径说明</h3>"
                   + _table(["项", "取值"],
                            [["口径版本", (c7.get("caliber") or {}).get("version")],
                             ["冷机容量放大系数", (c7.get("caliber") or {}).get("capacityFactor")],
                             ["碳排放因子(kgCO2/kWh)", carbon.get("value")],
                             ["因子地理层级", label_carbon_level(carbon.get("level"))],
                             ["因子核算年度", carbon.get("year")],
                             ["因子来源", carbon.get("source")]], numeric_from=1)
                   + extrap_note)

    order = view.get("chapterOrder") or ["1", "2", "3", "4", "5", "6", "7"]
    parts = {"1": ch1, "2": ch2, "3": ch3, "4": ch4, "5": ch5, "6": ch6, "7": ch7}
    body = "".join(parts[k] for k in order)
    title = f'{_value_of(cover_items, "projectName") or "未命名项目"} — 全年冷源站能耗仿真报告'
    return ('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
            f'<title>{_esc(title)}</title><style>{_CSS}</style></head><body>{body}</body></html>')


def list_reports_for_task(task_id: str) -> List[Dict[str, Any]]:
    """列出某任务的全部历史报告（按生成时间倒序）。"""
    out: List[Dict[str, Any]] = []
    if not os.path.isdir(REPORTS_DIR):
        return out
    for name in os.listdir(REPORTS_DIR):
        meta_path = os.path.join(REPORTS_DIR, name, "meta.json")
        if name.endswith(".tmp") or not os.path.isfile(meta_path):
            continue
        try:
            with open(meta_path, "r", encoding="utf-8") as fp:
                meta = _json.load(fp)
        except (OSError, ValueError):
            continue
        if meta.get("taskId") == task_id:
            out.append({
                "reportId": meta.get("reportId"),
                "generatedAt": meta.get("generatedAt"),
                "caliberVersion": meta.get("caliberVersion"),
                "reportVersion": meta.get("reportVersion"),
            })
    return sorted(out, key=lambda x: x.get("generatedAt") or "", reverse=True)


def read_report_meta(report_id: str) -> Dict[str, Any]:
    """读取已生成报告的 meta.json；不存在则抛 FileNotFoundError。"""
    path = os.path.join(REPORTS_DIR, report_id, "meta.json")
    if not os.path.isfile(path):
        raise FileNotFoundError(report_id)
    with open(path, "r", encoding="utf-8") as fp:
        return _json.load(fp)


def report_html_path(report_id: str) -> str:
    """返回已生成报告的 html 路径；不存在则抛 FileNotFoundError。"""
    path = os.path.join(REPORTS_DIR, report_id, "report.html")
    if not os.path.isfile(path):
        raise FileNotFoundError(report_id)
    return path


def write_report_snapshot(report_id: str, html: str, view: Dict[str, Any],
                          result: Dict[str, Any], owner_id: Any = None) -> str:
    """原子写入报告目录（4.2/4.3）：先写 .tmp，三份文件齐全后 rename；失败即清理。"""
    os.makedirs(REPORTS_DIR, exist_ok=True)
    final = os.path.join(REPORTS_DIR, report_id)
    tmp = os.path.join(REPORTS_DIR, report_id + ".tmp")
    if os.path.exists(final):
        raise FileExistsError(f"报告目录已存在: {report_id}")
    try:
        os.makedirs(tmp, exist_ok=False)
        meta = {
            "reportId": report_id,
            "taskId": view.get("taskId"),
            # 归属用户：服务重启后内存任务已失，鉴权只能依赖快照里的这个字段（任务 5.4/5.5）
            "ownerId": owner_id,
            "reportVersion": view.get("reportVersion"),
            "caliberVersion": view.get("caliberVersion"),
            "generatedAt": view.get("generatedAt") or _now_iso(),
            "carbonFactor": (view.get("chapters", {}).get("7", {}) or {}).get("carbon") or {},
            "chapterOrder": view.get("chapterOrder"),
            "chapterTitles": view.get("chapterTitles"),
        }
        with open(os.path.join(tmp, "report.html"), "w", encoding="utf-8") as fp:
            fp.write(html)
        with open(os.path.join(tmp, "result.json"), "w", encoding="utf-8") as fp:
            fp.write(_json.dumps(result, ensure_ascii=False, indent=1, default=str))
        with open(os.path.join(tmp, "meta.json"), "w", encoding="utf-8") as fp:
            fp.write(_json.dumps(meta, ensure_ascii=False, indent=1, default=str))
        for name in ("report.html", "result.json", "meta.json"):
            if not os.path.exists(os.path.join(tmp, name)):
                raise OSError(f"快照文件缺失: {name}")
        os.rename(tmp, final)
        return final
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        raise


