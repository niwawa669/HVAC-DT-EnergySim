"""
算法包装器 - 将您的冷站仿真算法接入 API 服务
"""
import sys
import os
import json
import math
import random
from typing import Dict, Any, List, Optional, Iterator
import pandas as pd

# ===== 添加算法路径 =====
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.join(CURRENT_DIR, '../../..')
ALGORITHM_PATH = os.path.join(PROJECT_ROOT, 'algorithm')

if ALGORITHM_PATH not in sys.path:
    sys.path.insert(0, ALGORITHM_PATH)

print(f"算法路径: {ALGORITHM_PATH}")

# ===== 碳排放因子配置（D10；数据源见 docs/data-contract.md 与 docs/references/） =====
EMISSION_FACTOR_FILE = os.path.join(CURRENT_DIR, '..', 'config', 'emission_factors.json')
EMISSION_FACTOR_FALLBACK = 0.5554  # 北京 2023，配置不可用时的兜底值


def load_emission_factors():
    """读取排放因子配置；失败时返回 None，由调用方使用兜底值"""
    try:
        with open(EMISSION_FACTOR_FILE, 'r', encoding='utf-8') as fp:
            return json.load(fp)
    except Exception as exc:
        print(f"⚠️ 读取排放因子配置失败: {exc}")
        return None

# ============================================
# 尝试导入您的算法模块
# ============================================
ALGORITHM_AVAILABLE = False
Station = None
StationInfo = None

try:
    from station import Station, StationInfo
    ALGORITHM_AVAILABLE = True
    print("✅ 算法模块导入成功")
except ImportError as e:
    print(f"⚠️ 算法导入失败: {e}")
    print("将使用模拟模式")


class AlgorithmWrapper:
    """算法包装器"""

    # 允许出现在 config 中的参数（D7/6.5）：不在此列表中的参数必须在启动前报错，
    # 而不是被静默丢弃。新增参数时请同步维护本集合。
    KNOWN_PARAMS = {
        # 建筑负荷与量纲
        'load_building_r', 'load_coe',
        # 冷机
        'Qr_chiller_BCH', 'n_design_BCH', 'COP_chiller_BCH',
        'Qr_chiller_SCH', 'n_design_SCH', 'COP_chiller_SCH',
        'ts_chw_design', 'tr_chw_design', 'tr_cw_design', 'ts_cw_design',
        # 冷冻泵
        'Gr_pump_chw_BCH', 'Hr_pump_chw_BCH', 'n_pump_chw_BCH',
        'Gr_pump_chw_SCH', 'Hr_pump_chw_SCH', 'n_pump_chw_SCH',
        # 冷却泵
        'Gr_pump_cw_BCH', 'Hr_pump_cw_BCH', 'n_pump_cw_BCH',
        'Gr_pump_cw_SCH', 'Hr_pump_cw_SCH', 'n_pump_cw_SCH',
        # 冷却塔
        'Gr_tower_BCH', 'Pr_tower_BCH', 'Hs_tower_BCH', 'n_tower_BCH',
        'Gr_tower_SCH', 'Pr_tower_SCH', 'Hs_tower_SCH', 'n_tower_SCH',
        # 管道压降
        'Hr_pt', 'Hr_chiller_chw_BCH', 'Hr_chiller_cw_BCH',
        'Hr_chiller_chw_SCH', 'Hr_chiller_cw_SCH',
        # 群控：温度、负荷、台数序列、频率
        'ta_dry_r', 'ta_wet_r', 'ts_chw_set', 'delta_t_chw', 'delta_t_cw',
        'tr_cw_min', 'approach_set', 'load_up', 'load_min',
        'Qr_list', 'n_design_list',
        'freq_pump_max', 'freq_pump_min', 'freq_tower_max', 'freq_tower_min',
        # 口径与披露（D10/D11）
        'carbon_year', 'carbon_province', 'applicable_range',
    }

    def __init__(self):
        self.station_info = None
        self.station = None
        self._last_summary = {}
        self._last_weekly_data = []
        self._initialize_station()
    
    def _initialize_station(self):
        """初始化冷站配置"""
        if not ALGORITHM_AVAILABLE or StationInfo is None:
            print("⚠️ 算法不可用，使用模拟模式")
            return
        
        try:
            self.station_info = StationInfo()
            self.station = Station(self.station_info)  # type: ignore
            print("✅ 冷站仿真算法初始化完成")
        except Exception as e:
            print(f"❌ 冷站初始化失败: {e}")
            self.station = None
    
    def validate_config(self, config: Optional[Dict[str, Any]]) -> None:
        """启动前校验参数是否全部被映射（6.5）：不通过则抛 ValueError 并指名参数"""
        if not config:
            return
        unknown = sorted(set(config) - self.KNOWN_PARAMS)
        if unknown:
            raise ValueError(f"存在未映射参数，拒绝启动仿真: {', '.join(unknown)}")

    def update_station_config(self, config: Dict[str, Any]) -> bool:
        """
        根据前端传入的配置更新冷站参数
        
        Args:
            config: 前端传递的配置字典，包含设备选型和群控参数
        
        Returns:
            是否更新成功
        """
        if not ALGORITHM_AVAILABLE or StationInfo is None:
            print("⚠️ 算法不可用，跳过配置更新")
            return False
        
        unknown = sorted(set(config) - self.KNOWN_PARAMS)
        if unknown:
            raise ValueError(f"存在未映射参数，拒绝启动仿真: {', '.join(unknown)}")

        try:
            # 创建新的 StationInfo 实例
            self.station_info = StationInfo()
            
            # ===== 映射设备选型参数 =====
            # 建筑负荷
            if 'load_building_r' in config:
                self.station_info.load_building_r = config['load_building_r']
            if 'load_coe' in config:
                # 量纲换算系数：单一来源，默认 0.001（W->kW，口径 v1）
                self.station_info.load_coe = float(config['load_coe'])
            
            # 冷机参数
            if 'Qr_chiller_BCH' in config:
                self.station_info.Qr_chiller_BCH = config['Qr_chiller_BCH']
            if 'n_design_BCH' in config:
                self.station_info.n_design_BCH = config['n_design_BCH']
            if 'Qr_chiller_SCH' in config:
                self.station_info.Qr_chiller_SCH = config['Qr_chiller_SCH']
            if 'n_design_SCH' in config:
                self.station_info.n_design_SCH = config['n_design_SCH']
            
            # 冷机水温参数
            if 'ts_chw_design' in config:
                self.station_info.ts_chw_set = config['ts_chw_design']
            if 'tr_chw_design' in config:
                # 回水温度 = 供水温度 + 温差
                self.station_info.delta_t_chw = config['tr_chw_design'] - config.get('ts_chw_design', 7.0)
            if 'tr_cw_design' in config:
                self.station_info.tr_cw_design_BCH = config['tr_cw_design']
                self.station_info.tr_cw_design_SCH = config['tr_cw_design']
            if 'ts_cw_design' in config:
                self.station_info.ts_cw_design_BCH = config['ts_cw_design']
                self.station_info.ts_cw_design_SCH = config['ts_cw_design']
            
            # 设备台数（D7：作为功率乘数，不再一律按冷机台数）
            for key, attr in (
                ('n_pump_chw_BCH', 'n_pump_chw_BCH'), ('n_pump_chw_SCH', 'n_pump_chw_SCH'),
                ('n_pump_cw_BCH', 'n_pump_cw_BCH'), ('n_pump_cw_SCH', 'n_pump_cw_SCH'),
                ('n_tower_BCH', 'n_tower_BCH'), ('n_tower_SCH', 'n_tower_SCH'),
            ):
                if key in config and config[key] is not None:
                    setattr(self.station_info, attr, int(config[key]))

            # 冷冻泵参数
            if 'Gr_pump_chw_BCH' in config:
                self.station_info.Gr_pump_chw_BCH = config['Gr_pump_chw_BCH']
            if 'Hr_pump_chw_BCH' in config:
                self.station_info.Hr_pump_chw_BCH = config['Hr_pump_chw_BCH']
            if 'Gr_pump_chw_SCH' in config:
                self.station_info.Gr_pump_chw_SCH = config['Gr_pump_chw_SCH']
            if 'Hr_pump_chw_SCH' in config:
                self.station_info.Hr_pump_chw_SCH = config['Hr_pump_chw_SCH']
            
            # 冷却泵参数
            if 'Gr_pump_cw_BCH' in config:
                self.station_info.Gr_pump_cw_BCH = config['Gr_pump_cw_BCH']
            if 'Hr_pump_cw_BCH' in config:
                self.station_info.Hr_pump_cw_BCH = config['Hr_pump_cw_BCH']
            if 'Gr_pump_cw_SCH' in config:
                self.station_info.Gr_pump_cw_SCH = config['Gr_pump_cw_SCH']
            if 'Hr_pump_cw_SCH' in config:
                self.station_info.Hr_pump_cw_SCH = config['Hr_pump_cw_SCH']
            
            # 冷却塔参数
            if 'Gr_tower_BCH' in config:
                self.station_info.Gr_tower_BCH = config['Gr_tower_BCH']
            if 'Pr_tower_BCH' in config:
                self.station_info.Pr_tower_BCH = config['Pr_tower_BCH']
            if 'Hs_tower_BCH' in config:
                self.station_info.Hs_tower_BCH = config['Hs_tower_BCH']
            if 'Gr_tower_SCH' in config:
                self.station_info.Gr_tower_SCH = config['Gr_tower_SCH']
            if 'Pr_tower_SCH' in config:
                self.station_info.Pr_tower_SCH = config['Pr_tower_SCH']
            if 'Hs_tower_SCH' in config:
                self.station_info.Hs_tower_SCH = config['Hs_tower_SCH']
            
            # 管道压降
            if 'Hr_pt' in config:
                self.station_info.Hr_pt = config['Hr_pt']
            if 'Hr_chiller_chw_BCH' in config:
                self.station_info.Hr_chiller_chw_BCH = config['Hr_chiller_chw_BCH']
            if 'Hr_chiller_cw_BCH' in config:
                self.station_info.Hr_chiller_cw_BCH = config['Hr_chiller_cw_BCH']
            if 'Hr_chiller_chw_SCH' in config:
                self.station_info.Hr_chiller_chw_SCH = config['Hr_chiller_chw_SCH']
            if 'Hr_chiller_cw_SCH' in config:
                self.station_info.Hr_chiller_cw_SCH = config['Hr_chiller_cw_SCH']
            
            # ===== 映射群控控制参数 =====
            # 温度控制
            if 'ta_dry_r' in config:
                self.station_info.ta_dry_r = config['ta_dry_r']
            if 'ta_wet_r' in config:
                self.station_info.ta_wet_r = config['ta_wet_r']
            if 'ts_chw_set' in config:
                self.station_info.ts_chw_set = config['ts_chw_set']
            if 'delta_t_chw' in config:
                self.station_info.delta_t_chw = config['delta_t_chw']
            if 'delta_t_cw' in config:
                self.station_info.delta_t_cw = config['delta_t_cw']
            if 'tr_cw_min' in config:
                self.station_info.tr_cw_min = config['tr_cw_min']
            if 'approach_set' in config:
                self.station_info.approach_set = config['approach_set']
            
            # 负荷控制
            if 'load_up' in config:
                self.station_info.load_up = config['load_up']
            if 'load_min' in config:
                self.station_info.load_min = config['load_min']
            
            # 冷机加机优先级
            if 'Qr_list' in config and isinstance(config['Qr_list'], list):
                self.station_info.Qr_list = config['Qr_list']
            if 'n_design_list' in config and isinstance(config['n_design_list'], list):
                self.station_info.n_design_list = config['n_design_list']
            
            # 频率控制
            if 'freq_pump_max' in config and 'freq_pump_min' in config:
                self.station_info.ratio_Hz_min_pump = config['freq_pump_min'] / config['freq_pump_max']
            if 'freq_tower_max' in config and 'freq_tower_min' in config:
                self.station_info.ratio_Hz_min_tower = config['freq_tower_min'] / config['freq_tower_max']
            
            # ===== 重新创建 Station 实例 =====
            self.station = Station(self.station_info)  # type: ignore
            
            return True
            
        except Exception as e:
            print(f"❌ 更新冷站配置失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    # ===== 碳排放因子选择（D10）=====
    def _resolve_emission_factor(self, config: Dict[str, Any]):
        """按「省级 → 区域 → 全国」逐级回退选择因子，返回 (值, 层级, 年度, 来源, 是否回退)"""
        cfg = load_emission_factors()
        if not cfg:
            return EMISSION_FACTOR_FALLBACK, 'fallback', '-', '内置兜底值', True
        default_sel = cfg.get('default_selection', {})
        year = str(config.get('carbon_year') or default_sel.get('year') or '2023')
        factors_all = cfg.get('factors', {})
        if year not in factors_all:
            year = str(default_sel.get('year') or next(iter(factors_all)))
        factors = factors_all.get(year, {})
        province = config.get('carbon_province') or default_sel.get('province')

        value, level, fallback = None, None, False
        if province and province in factors.get('provincial', {}):
            value, level = factors['provincial'][province], 'provincial'
        else:
            fallback = True
            region = (cfg.get('province_to_region') or {}).get(province) if province else None
            if region and region in factors.get('regional', {}):
                value, level = factors['regional'][region], 'regional'
            else:
                value, level = factors.get('national', {}).get('average'), 'national'
        if value is None:
            return EMISSION_FACTOR_FALLBACK, 'fallback', year, '内置兜底值', True
        src = (cfg.get('sources') or {}).get(year, {})
        source_text = f"{src.get('title', '')}（{src.get('issuer', '')}，{src.get('published', '')}）"
        return float(value), level, year, source_text, fallback

    def _display_only_deviations(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """仅展示参数的标称值 vs 模型值偏差（D7/6.3）

        COP_chiller_* 与 Pr_tower_* 不参与能耗计算，但若直接删除会让选型表失去可比性，
        因此降级为「仅展示」并赋予标称校核用途——使 D5 的线性缩放假设可被观察。
        """
        st = self.station
        si = self.station_info
        out: Dict[str, Any] = {}
        if st is None or si is None:
            return out

        ts_chw = float(si.ts_chw_set)
        tr_chw = ts_chw + float(si.delta_t_chw)
        for tag, channel, tr_cw, ts_cw in (
            ('BCH', st.channel_BCH, float(si.tr_cw_design_BCH), float(si.ts_cw_design_BCH)),
            ('SCH', st.channel_SCH, float(si.tr_cw_design_SCH), float(si.ts_cw_design_SCH)),
        ):
            ch = channel.chiller
            p_model = ch(1.0, tr_chw, ts_chw, tr_cw, ts_cw)
            cop_model = (ch.Q_r / p_model) if p_model else 0.0
            nominal = config.get(f'COP_chiller_{tag}')
            out[f'COP_chiller_{tag}'] = {
                'nominal': nominal,
                'model': cop_model,
                'deviationRatio': ((float(nominal) - cop_model) / cop_model)
                                  if (nominal is not None and cop_model) else None,
                'role': 'display_only',
            }

        for tag, channel, nominal_key in (
            ('BCH', st.channel_BCH, 'Pr_tower_BCH'),
            ('SCH', st.channel_SCH, 'Pr_tower_SCH'),
        ):
            tw = channel.tower
            _, p_model = tw(tw.t_dry_r, tw.da_r, tw.ts_cw_r, tw.Gw_r, tw.Ga_r)
            nominal = config.get(nominal_key)
            out[nominal_key] = {
                'nominal': nominal,
                'model': float(p_model),
                'deviationRatio': ((float(nominal) - float(p_model)) / float(p_model))
                                  if (nominal is not None and p_model) else None,
                'role': 'display_only',
            }
        return out

    def _extrapolation_stats(self, hours: List[Dict[str, Any]], config: Dict[str, Any]):
        """模型适用范围外推统计（D11）：范围由用户配置，须在结果中声明"""
        rng = config.get('applicable_range') or {}
        t_lo = float(rng.get('t_dry_min', -20.0))
        t_hi = float(rng.get('t_dry_max', 40.0))
        d_lo = float(rng.get('d_min', 0.0))
        d_hi = float(rng.get('d_max', 0.03))
        outside = [h for h in hours
                   if not (t_lo <= h['temp'] <= t_hi and d_lo <= h['humid'] <= d_hi)]
        energy = sum(h['ec_chiller'] + h['ec_pump_chw'] + h['ec_pump_cw'] + h['ec_tower']
                     for h in outside)
        return {
            'range': {'t_dry_min': t_lo, 't_dry_max': t_hi, 'd_min': d_lo, 'd_max': d_hi},
            'hours': len(outside),
            'ratio': (len(outside) / len(hours)) if hours else 0.0,
            'energy': energy,
            'source': 'user_configured',
            'note': '范围为用户声明值，不是模型真实训练域',
        }

    def run_simulation_streaming(
        self, 
        data: List[Dict[str, Any]], 
        config: Optional[Dict[str, Any]] = None,
        area: float = 2931.0,
        meta: Optional[Dict[str, Any]] = None
    ) -> Iterator[Dict[str, Any]]:
        """
        流式运行仿真计算 - 每计算完一周立即 yield 结果
        """
        # ===== 更新配置 =====
        if config:
            self.update_station_config(config)
        
        if not ALGORITHM_AVAILABLE or self.station is None:
            print("⚠️ 算法不可用，使用模拟流式模式")
            yield from self._run_mock_simulation_streaming(data, area)
            return
        
        if not data or len(data) == 0:
            raise ValueError("数据为空")
        
        df = pd.DataFrame(data)

        # ===== 时间轴（D1）：首列即时间戳，全程携带，不再用 index//168 推算 =====
        time_col = df.columns[0]
        ts = pd.to_datetime(df[time_col], errors='coerce')
        n_bad = int(ts.isna().sum())
        if n_bad > 0:
            raise ValueError(f"首列时间戳有 {n_bad} 行无法解析，请按 YYYY-MM-DD HH:00 格式提供")

        # 查找列名
        load_col = self._find_column(df, ['load', '负荷', '冷负荷', 'cooling_load'])
        temp_col = self._find_column(df, ['t_dry', '干球温度', '温度', 'temp', 'temperature'])
        humid_col = self._find_column(df, ['d', '含湿量', '湿度', 'humidity'])

        if load_col is None:
            raise ValueError("未找到负荷列")

        print(f"检测到列: 时间={time_col}, 负荷={load_col}, 温度={temp_col}, 含湿量={humid_col}")

        df = df.copy()
        df['_ts'] = ts
        iso = ts.dt.isocalendar()
        # 日历周（ISO，周一为周首）与自然月作为分组键（D2）
        df['_wkey'] = iso['year'].astype(str) + '-W' + iso['week'].astype(str).str.zfill(2)
        df['_mkey'] = ts.dt.strftime('%Y-%m')

        total_hours = len(df)
        processed_hours = 0
        week_no = 0
        all_hours = []
        all_weekly_results = []

        for wkey, wdf in df.groupby('_wkey', sort=True):
            week_no += 1
            hours = [self._compute_hour(t, l, tp, h)
                     for t, l, tp, h in self._iter_rows(wdf, load_col, temp_col, humid_col)]
            if not hours:
                continue
            all_hours.extend(hours)
            processed_hours += len(hours)

            agg = self._aggregate(hours)
            week_result = {
                'weekNumber': week_no,
                'weekLabel': wkey,
                'weekStart': agg['start'],
                'weekEnd': agg['end'],
                'hours': agg['hours'],
                'totalCoolingLoad': agg['totalCoolingLoad'],
                'peakCoolingLoad': agg['peakCoolingLoad'],
                'totalQStation': agg['totalQStation'],
                'totalEnergyConsumption': agg['totalEnergyConsumption'],
                'avgSystemCop': agg['systemEER'],      # 兼容旧字段名，语义为系统能效
                'avgChillerCop': agg['avgChillerCop'],  # 冷机平均 COP（与系统能效分离，D4）
                'avgOutdoorTemp': agg['avgOutdoorTemp'],
                'breakdown': agg['breakdown'],
                'supplyGap': agg['totalUnmet'],
                'unservedWhenOff': agg['totalUnservedOff'],
                'unmetHours': agg['unmetHours'],
                'progressPercentage': round(processed_hours / total_hours * 100.0, 2),
            }
            yield week_result
            all_weekly_results.append(week_result)

            if week_no % 10 == 0:
                print(f"仿真进度: {week_no} 周 / {processed_hours} 小时")

        # ===== 全量聚合（全年 + 自然月 + 运行统计 + 尖峰）=====
        year = self._aggregate(all_hours)
        self._last_weekly_data = all_weekly_results
        self._last_monthly_data = [
            dict(self._aggregate(list(g)), month=k)
            for k, g in self._group_by_month(all_hours)
        ]
        self._last_hours = all_hours
        self._last_year_agg = year

        # ===== 逐时缺口明细（可定位到具体小时，供报告与复核使用）=====
        self._last_unmet_hours = [
            {
                'timestamp': h['timestamp'],
                'demand': h['load'],
                'served': h['q_station'],
                'unmet': h['unmet'],
                'loadRate': h['load_rate'],
                'nSCH': h['n_sch'],
                'nBCH': h['n_bch'],
                'temperature': h['temp'],
            }
            for h in all_hours if h['unmet'] > 0
        ]

        # ===== 元信息：数据溯源 + 项目标识 + 碳排口径 + 适用范围（4.3/4.4/4.5）=====
        provided = dict(meta or {})
        cfg = config or {}
        factor, factor_level, factor_year, factor_source, factor_fallback = \
            self._resolve_emission_factor(cfg)
        extrap = self._extrapolation_stats(all_hours, cfg)
        self._last_emission_factor = factor

        t_dry = [h['temp'] for h in all_hours]
        humid = [h['humid'] for h in all_hours]
        self._last_meta = {
            # 数据溯源
            'fileName': provided.get('fileName'),
            'totalRows': provided.get('totalRows', len(all_hours)),
            'totalHours': len(all_hours),
            'startTime': all_hours[0]['timestamp'] if all_hours else None,
            'endTime': all_hours[-1]['timestamp'] if all_hours else None,
            'confirmedRange': provided.get('confirmedRange'),
            'correctedOutliers': provided.get('correctedOutliers', 0),
            'tDryMin': min(t_dry) if t_dry else None,
            'tDryMax': max(t_dry) if t_dry else None,
            'humidMin': min(humid) if humid else None,
            'humidMax': max(humid) if humid else None,
            'weeks': len(all_weekly_results),
            # 项目标识
            'projectName': provided.get('projectName'),
            'buildingType': provided.get('buildingType'),
            'area': provided.get('area', area),
            # 口径
            'caliberVersion': 'v1',
            'loadCoe': cfg.get('load_coe') if cfg.get('load_coe') is not None
                        else getattr(self.station_info, 'load_coe', None),
            # 碳排口径
            'carbonFactor': {
                'value': factor,
                'unit': 'kgCO2/kWh',
                'level': factor_level,
                'year': factor_year,
                'source': factor_source,
                'fallback': factor_fallback,
            },
            # 模型适用范围与外推
            'applicableRange': extrap['range'],
            'applicableRangeSource': extrap['source'],
            'extrapolation': {
                'hours': extrap['hours'],
                'ratio': extrap['ratio'],
                'energy': extrap['energy'],
                'note': extrap['note'],
            },
            # 参数快照（4.4/6.5）
            'parameters': provided.get('parameters') or cfg,
            'displayOnly': provided.get('displayOnly') or ['COP_chiller_BCH', 'COP_chiller_SCH',
                                                            'Pr_tower_BCH', 'Pr_tower_SCH'],
            'displayOnlyDeviations': self._display_only_deviations(cfg),
        }
        self._last_summary = {
            'totalEnergy': year['totalEnergyConsumption'],
            'totalCoolingLoad': year['totalCoolingLoad'],
            'totalQStation': year['totalQStation'],
            'eui': year['totalEnergyConsumption'] / area if area > 0 else 0,
            'peakCoolingLoad': year['peakCoolingLoad'],
            'peakHeatingLoad': 0,
            'avgCop': year['avgChillerCop'],
            'systemEER': year['systemEER'],
            'totalUnmet': year['totalUnmet'],
            'unmetHours': year['unmetHours'],
            'totalUnservedOff': year['totalUnservedOff'],
            'breakdown': year['breakdown'],
            'operatingStats': year['operatingStats'],
            'peakContext': year['peakContext'],
            'loadRateHistogram': year['loadRateHistogram'],
            'carbonEmission': year['totalEnergyConsumption'] * factor,
            'area': area
        }

        print(f"仿真完成: 小时数={len(all_hours)}, 总能耗={year['totalEnergyConsumption']:.2f} kWh, "
              f"总供冷量={year['totalQStation']:.2f} kWh, 系统能效={year['systemEER']:.2f}")
    
    # ===== 逐时计算与聚合（D1/D2/D3/D4/D6）=====
    def _iter_rows(self, df, load_col, temp_col, humid_col):
        """按输入顺序产出 (时间戳, 负荷, 干球温度, 含湿量)"""
        for _, row in df.iterrows():
            t = row.get('_ts')
            load = float(row[load_col]) if pd.notna(row[load_col]) else 0.0
            load = max(load, 0.0)
            temp = float(row[temp_col]) if (temp_col and pd.notna(row[temp_col])) else 25.0
            humid = float(row[humid_col]) if (humid_col and pd.notna(row[humid_col])) else 0.01
            yield t, load, temp, humid

    def _compute_hour(self, ts, load, temp, humid) -> Dict[str, Any]:
        """单点仿真并返回带时间戳的逐时记录"""
        result = self._run_single_point(load, temp, humid)
        st = self.station
        if result:
            q = float(result.get('制冷量(kWh)', 0.0))
            ec_ch = float(result.get('冷机耗电量(kWh)', 0.0))
            ec_pw = float(result.get('冷冻泵耗电量(kWh)', 0.0))
            ec_cw = float(result.get('冷却泵耗电量(kWh)', 0.0))
            ec_tw = float(result.get('冷却塔耗电量(kWh)', 0.0))
            cop = float(result.get('冷机COP', 0.0))
            eers = float(result.get('冷站EERs', 0.0))
            unmet = float(result.get('供冷缺口(kWh)', 0.0))
            off = float(result.get('停机未供冷量(kWh)', 0.0))
        else:
            q = ec_ch = ec_pw = ec_cw = ec_tw = cop = eers = unmet = off = 0.0

        # 冷负荷统一换算到计算量纲（kW），保证与供冷量可比
        load_coe = float(getattr(self.station_info, 'load_coe', 1.0) or 1.0)
        load_kw = load * load_coe

        n_active = list(st.n_active_list) if st is not None and st.n_active_list else []
        n_sch = float(n_active[0]) if len(n_active) > 0 else 0.0
        n_bch = float(n_active[1]) if len(n_active) > 1 else 0.0
        installed = float(getattr(st, 'Q_installed_active', 0.0) or 0.0)
        load_rate = (q / installed) if installed > 0 else 0.0

        return {
            'timestamp': pd.Timestamp(ts).isoformat() if ts is not None else None,
            'month': pd.Timestamp(ts).strftime('%Y-%m') if ts is not None else None,
            'load': load_kw, 'load_raw': load, 'temp': temp, 'humid': humid,
            'q_station': q,
            'ec_chiller': ec_ch, 'ec_pump_chw': ec_pw, 'ec_pump_cw': ec_cw, 'ec_tower': ec_tw,
            'cop_chiller': cop, 'eers': eers,
            'unmet': unmet, 'unserved_off': off,
            'n_sch': n_sch, 'n_bch': n_bch,
            'load_rate': load_rate,
        }

    def _group_by_month(self, hours):
        buckets = {}
        for h in hours:
            buckets.setdefault(h['month'], []).append(h)
        return sorted(buckets.items())

    def _aggregate(self, hours: List[Dict[str, Any]]) -> Dict[str, Any]:
        """把逐时记录聚合为周/月/年三个层次通用的统计块"""
        n = len(hours)
        agg = {
            'start': hours[0]['timestamp'] if n else None,
            'end': hours[-1]['timestamp'] if n else None,
            'hours': n,
            'totalCoolingLoad': 0.0, 'peakCoolingLoad': 0.0, 'totalQStation': 0.0,
            'totalEnergyConsumption': 0.0,
            'breakdown': {'chiller': 0.0, 'pump_chw': 0.0, 'pump_cw': 0.0, 'tower': 0.0},
            'totalUnmet': 0.0, 'unmetHours': 0, 'totalUnservedOff': 0.0,
            'avgChillerCop': 0.0, 'systemEER': 0.0, 'avgOutdoorTemp': 0.0,
            'operatingStats': {}, 'loadRateHistogram': [0] * 10, 'peakContext': None,
        }
        if n == 0:
            return agg

        cop_sum = cop_cnt = 0.0
        temp_sum = 0.0
        op = {}
        hist = [0] * 10
        peak = None

        for h in hours:
            agg['totalCoolingLoad'] += h['load']
            agg['totalQStation'] += h['q_station']
            agg['peakCoolingLoad'] = max(agg['peakCoolingLoad'], h['load'])
            agg['totalUnmet'] += h['unmet']
            agg['totalUnservedOff'] += h['unserved_off']
            if h['unmet'] > 0:
                agg['unmetHours'] += 1
            agg['breakdown']['chiller'] += h['ec_chiller']
            agg['breakdown']['pump_chw'] += h['ec_pump_chw']
            agg['breakdown']['pump_cw'] += h['ec_pump_cw']
            agg['breakdown']['tower'] += h['ec_tower']
            temp_sum += h['temp']
            if h['cop_chiller'] > 0:
                cop_sum += h['cop_chiller']
                cop_cnt += 1
            if h['n_sch'] > 0:
                op['SCH'] = op.get('SCH', 0) + 1
            if h['n_bch'] > 0:
                op['BCH'] = op.get('BCH', 0) + 1
            if h['q_station'] > 0:
                idx = min(int(h['load_rate'] * 10), 9)
                hist[idx] += 1
            if peak is None or h['load'] > peak['load']:
                peak = h

        bd = agg['breakdown']
        agg['totalEnergyConsumption'] = bd['chiller'] + bd['pump_chw'] + bd['pump_cw'] + bd['tower']
        agg['avgChillerCop'] = cop_sum / cop_cnt if cop_cnt > 0 else 0.0
        agg['systemEER'] = (agg['totalQStation'] / agg['totalEnergyConsumption']
                            if agg['totalEnergyConsumption'] > 0 else 0.0)
        agg['avgOutdoorTemp'] = temp_sum / n
        agg['operatingStats'] = op
        agg['loadRateHistogram'] = hist
        if peak is not None:
            agg['peakContext'] = {
                'timestamp': peak['timestamp'], 'load': peak['load'],
                'loadUnit': 'kW', 'loadRaw': peak.get('load_raw'),
                'temperature': peak['temp'], 'humid': peak['humid'],
                'qStation': peak['q_station'], 'chillerCOP': peak['cop_chiller'],
                'systemEER': peak['eers'], 'loadRate': peak['load_rate'],
                'nSCH': peak['n_sch'], 'nBCH': peak['n_bch'],
            }
        return agg


    def _run_single_point(self, load: float, temp: float, humid: float) -> Optional[Dict[str, Any]]:
        """运行单点仿真"""
        if self.station is None:
            return None
        
        try:
            result = self.station(load, temp, humid)
            return result
        except Exception as e:
            print(f"❌ 单点仿真错误: {e}")
            return None
    
    def _find_column(self, df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
        """查找列名"""
        for candidate in candidates:
            if candidate in df.columns:
                return candidate
            for col in df.columns:
                if col.lower() == candidate.lower():
                    return col
        return None
    
    def get_last_summary(self) -> Dict[str, Any]:
        """获取最后一次仿真的汇总结果"""
        return self._last_summary
    
    def get_last_weekly_data(self) -> List[Dict[str, Any]]:
        """获取最后一次仿真的周度数据"""
        return self._last_weekly_data

    def get_last_monthly_data(self) -> List[Dict[str, Any]]:
        """获取最后一次仿真的月度数据"""
        return getattr(self, '_last_monthly_data', [])

    def get_last_meta(self) -> Dict[str, Any]:
        """获取最后一次仿真的元信息"""
        return getattr(self, '_last_meta', {})

    def get_last_unmet_hours(self) -> List[Dict[str, Any]]:
        """获取逐时供冷缺口明细（仅包含存在缺口的小时）"""
        return getattr(self, '_last_unmet_hours', [])
    
    def _run_mock_simulation_streaming(self, data: List[Dict[str, Any]], area: float = 2931.0) -> Iterator[Dict[str, Any]]:
        """模拟流式仿真"""
        print("⚠️ 使用模拟流式仿真")
        
        total_p_station = 0.0
        total_load = 0.0
        total_q_station = 0.0
        peak_load = 0.0
        
        for week in range(1, 53):
            week_p_station = 1500 + random.uniform(0, 1500)
            cooling_load = 200 + random.uniform(0, 300)
            week_temp = 15 + 10 * math.sin((week / 52) * 2 * math.pi) + random.uniform(-2, 2)
            
            week_result = {
                'weekNumber': week,
                'totalCoolingLoad': cooling_load * 168,
                'peakCoolingLoad': cooling_load,
                'totalQStation': cooling_load * 168,
                'totalEnergyConsumption': week_p_station,
                'avgSystemCop': 3.0 + random.uniform(0, 0.5),
                'avgOutdoorTemp': week_temp,
            }
            
            total_p_station += week_p_station
            total_load += cooling_load * 168
            total_q_station += cooling_load * 168
            if cooling_load > peak_load:
                peak_load = cooling_load
            
            yield week_result
        
        self._last_summary = {
            'totalEnergy': total_p_station,
            'totalCoolingLoad': total_load,
            'totalQStation': total_q_station,
            'eui': total_p_station / area if area > 0 else 0,
            'peakCoolingLoad': peak_load,
            'peakHeatingLoad': 0,
            'avgCop': 3.2,
            'carbonEmission': total_p_station * 0.5,
            'area': area
        }


# 单例
algorithm_wrapper = AlgorithmWrapper()