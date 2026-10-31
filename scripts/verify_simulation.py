"""全年仿真自检脚本：复现一次完整仿真并核对三条外部可复核项。

用法（在项目根目录）：
    python scripts/verify_simulation.py

可选环境变量：
    PYTHONIOENCODING=utf-8   Windows 控制台下建议设置（算法层会打印 emoji）

三条可复核项：
    1. meta.totalHours 等于输入数据行数
    2. 分项能耗之和等于总耗电量
    3. 若供冷缺口大于 0，可定位到具体小时
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src" / "apiserver" / "app" / "services"))

import pandas as pd
import algorithm_wrapper as aw

CSV = ROOT / "src" / "algorithm" / "buildingload" / "buildingloads_adjusted.csv"


def main() -> int:
    w = aw.algorithm_wrapper
    df = pd.read_csv(CSV)
    rows = df.to_dict("records")

    cfg = {
        "applicable_range": {"t_dry_min": -20, "t_dry_max": 40, "d_min": 0, "d_max": 0.03},
    }
    meta_in = {"fileName": CSV.name, "totalRows": len(rows),
               "projectName": "自检项目", "buildingType": "office", "area": 2931.0}

    list(w.run_simulation_streaming(data=rows, config=cfg, area=2931.0, meta=meta_in))

    s = w._last_summary
    m = w._last_meta
    hours = w._last_hours

    print("=" * 62)
    print("仿真概览")
    print("=" * 62)
    print(f"计算小时数        : {m['totalHours']}（输入 {m['totalRows']} 行）")
    print(f"时间范围          : {m['startTime']} ~ {m['endTime']}")
    print(f"周数 / 月数       : {len(w._last_weekly_data)} / {len(w._last_monthly_data)}")
    si = w.station_info
    installed = si.Qr_chiller_BCH * si.n_design_BCH + si.Qr_chiller_SCH * si.n_design_SCH
    print(f"装机容量          : {installed:.2f} kW（设计负荷 {si.load_building_r * si.load_coe:.2f} kW 的 "
          f"{installed / (si.load_building_r * si.load_coe):.3f} 倍）")
    print(f"建筑总冷负荷      : {s['totalCoolingLoad']:.2f} kWh")
    print(f"冷源站总供冷量    : {s['totalQStation']:.2f} kWh")
    print(f"冷源站总耗电量    : {s['totalEnergy']:.2f} kWh")
    print(f"冷机平均 COP      : {s['avgCop']:.3f}")
    print(f"冷源站综合能效    : {s['systemEER']:.3f}")
    print(f"EUI               : {s['eui']:.3f} kWh/m2")
    cf = m["carbonFactor"]
    print(f"碳排放            : {s['carbonEmission']:.2f} kgCO2"
          f"（因子 {cf['value']} {cf['unit']}，{cf['year']} 年 {cf['level']}）")
    print(f"供冷缺口          : {s['totalUnmet']:.2f} kWh / {s['unmetHours']} 小时")
    print(f"停机未供冷        : {s['totalUnservedOff']:.2f} kWh")

    print()
    print("=" * 62)
    print("三条外部可复核项")
    print("=" * 62)
    ok1 = m["totalHours"] == m["totalRows"] == len(rows)
    print(f"[{'PASS' if ok1 else 'FAIL'}] 1. 总小时数 == 输入行数："
          f"{m['totalHours']} == {len(rows)}")

    bd = s["breakdown"]
    bd_sum = sum(bd.values())
    ok2 = abs(bd_sum - s["totalEnergy"]) < 1e-6
    print(f"[{'PASS' if ok2 else 'FAIL'}] 2. 分项加和 == 总耗电量："
          f"{bd_sum:.6f} == {s['totalEnergy']:.6f}")
    print(f"      冷机 {bd['chiller']:.2f} + 冷冻泵 {bd['pump_chw']:.2f} + "
          f"冷却泵 {bd['pump_cw']:.2f} + 冷却塔 {bd['tower']:.2f}")

    gap_hours = [h for h in hours if h["unmet"] > 0]
    if s["totalUnmet"] > 0:
        ok3 = len(gap_hours) == s["unmetHours"] and len(gap_hours) > 0
        print(f"[{'PASS' if ok3 else 'FAIL'}] 3. 缺口可定位：{len(gap_hours)} 小时，"
              f"前 3 条 -> {[(h['timestamp'], round(h['unmet'], 2)) for h in gap_hours[:3]]}")
    else:
        ok3 = True
        print("[PASS] 3. 供冷缺口为 0，无需定位")

    print()
    print(f"结论: {'全部通过' if (ok1 and ok2 and ok3) else '存在未通过项'}")
    return 0 if (ok1 and ok2 and ok3) else 1


if __name__ == "__main__":
    sys.exit(main())