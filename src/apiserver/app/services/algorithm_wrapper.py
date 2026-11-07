"""
算法包装器 - 将您的冷站仿真算法接入 API 服务
"""
import sys
import os
import json
import math
import random
from typing import Dict, Any, List, Optional, Iterator, Tuple
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
        # 建筑负荷与尺度
        'load_building_r', 'capacity_factor',
        # 冷机
        'Qr_chiller_BCH', 'n_design_BCH',
        'Qr_chiller_SCH', 'n_design_SCH',
        'ts_chw_design', 'tr_chw_design', 'tr_cw_design', 'ts_cw_design',
        # 冷冻泵
        'Hr_pump_chw_BCH', 'n_pump_chw_BCH',
        'Hr_pump_chw_SCH', 'n_pump_chw_SCH',
        # 冷却泵
        'Hr_pump_cw_BCH', 'n_pump_cw_BCH',
        'Hr_pump_cw_SCH', 'n_pump_cw_SCH',
        # 冷却塔
        'Pr_tower_BCH', 'Hs_tower_BCH', 'n_tower_BCH',
        'Pr_tower_SCH', 'Hs_tower_SCH', 'n_tower_SCH',
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
            self._apply_derived_design()
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
            if 'capacity_factor' in config:
                # 冷机容量放大系数（D4）：实际单机容量 = 基准容量 × 该系数
                self.station_info.capacity_factor = float(config['capacity_factor'])
            
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

            # 设计工况温度：界面上的供水温度与温差即算法使用的设定值
            if 'ts_chw_design' in config and config['ts_chw_design'] is not None:
                self.station_info.ts_chw_set = float(config['ts_chw_design'])

            # 冷冻泵参数（设计流量为派生值，仅接受水力阻力参数）
            if 'Hr_pump_chw_BCH' in config:
                self.station_info.Hr_pump_chw_BCH = config['Hr_pump_chw_BCH']
            if 'Hr_pump_chw_SCH' in config:
                self.station_info.Hr_pump_chw_SCH = config['Hr_pump_chw_SCH']

            # 冷却泵参数
            if 'Hr_pump_cw_BCH' in config:
                self.station_info.Hr_pump_cw_BCH = config['Hr_pump_cw_BCH']
            if 'Hr_pump_cw_SCH' in config:
                self.station_info.Hr_pump_cw_SCH = config['Hr_pump_cw_SCH']

            # 冷却塔参数（水流量派生自冷却泵；设计功率为用户输入）
            if 'Pr_tower_BCH' in config:
                self.station_info.Pr_tower_BCH = config['Pr_tower_BCH']
            if 'Hs_tower_BCH' in config:
                self.station_info.Hs_tower_BCH = config['Hs_tower_BCH']
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
            # 加机优先级序列未显式给出时，按实际台数推导，避免序列与台数脱节
            # （脱节会让群控按错误台数投运，且界面上看不出异常）
            _nlist = config.get('n_design_list')
            if isinstance(_nlist, list) and _nlist:
                self.station_info.n_design_list = list(_nlist)
            else:
                self.station_info.n_design_list = [
                    self.station_info.n_design_SCH, self.station_info.n_design_BCH
                ]
            
            # 频率控制
            if 'freq_pump_max' in config and 'freq_pump_min' in config:
                self.station_info.ratio_Hz_min_pump = config['freq_pump_min'] / config['freq_pump_max']
            if 'freq_tower_max' in config and 'freq_tower_min' in config:
                self.station_info.ratio_Hz_min_tower = config['freq_tower_min'] / config['freq_tower_max']
            
            # ===== 重新创建 Station 实例 =====
            # 设计工况派生量必须在 Station 构造之前注入，否则通道会拿到旧流量
            self._apply_derived_design()
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

    # 水的比热容 kJ/(kg·℃)，密度按 1 kg/L 计
    WATER_CP = 4.187
    # 模型参考冷机容量 kW
    MODEL_QR_REF = 2112.6

    # 设计工况派生量（D1）：由后端唯一计算，前端只展示
    DERIVED_PARAM_KEYS = {
        'COP_chiller_BCH', 'COP_chiller_SCH',
        'Gr_pump_chw_BCH', 'Gr_pump_chw_SCH',
        'Gr_pump_cw_BCH', 'Gr_pump_cw_SCH',
        'Gr_tower_BCH', 'Gr_tower_SCH',
    }

    def _design_cop(self, q_actual: float, tr_chw: float, ts_chw: float,
                    tr_cw: float, ts_cw: float) -> Optional[float]:
        """冷机模型在设计工况（满负荷）下的 COP。"""
        if not ALGORITHM_AVAILABLE or q_actual is None or q_actual <= 0:
            return None
        try:
            from chiller_model import Chiller
            scale = q_actual / self.MODEL_QR_REF
            chiller = Chiller(Q_r=q_actual, output_scale=scale)
            p = float(chiller(1.0, tr_chw, ts_chw, tr_cw, ts_cw))
            return (q_actual / p) if p > 0 else None
        except Exception as exc:  # pragma: no cover - 模型不可用时降级
            print(f"⚠️ 设计工况 COP 计算失败: {exc}")
            return None

    def _derive_flows(self, q_actual: float, cop: Optional[float],
                      dt_chw: float, dt_cw: float) -> Tuple[Optional[float], Optional[float]]:
        """由制冷量与 COP 推导冷冻/却却水设计流量 L/s（D1）。"""
        chw = cw = None
        if q_actual and dt_chw:
            chw = q_actual / (self.WATER_CP * dt_chw)
        if q_actual and dt_cw:
            heat = q_actual * (1.0 + 1.0 / cop) if cop else q_actual
            cw = heat / (self.WATER_CP * dt_cw)
        return chw, cw

    def _apply_derived_design(self) -> Dict[str, Any]:
        """计算并注入设计工况派生量，返回派生结果（供 meta 使用）。"""
        si = self.station_info
        if si is None:
            return {}
        cf = float(getattr(si, 'capacity_factor', 1.0) or 1.0)
        q_bch = si.Qr_chiller_BCH * cf
        q_sch = si.Qr_chiller_SCH * cf
        # 设计工况温度：冷冻水 = 供水设定值 / 供水 + 温差；冷却水取各通道设计值
        ts_chw = float(getattr(si, 'ts_chw_set', 7.0))
        tr_chw = ts_chw + float(getattr(si, 'delta_t_chw', 5.0))
        cop_bch = self._design_cop(q_bch, tr_chw, ts_chw,
                                   float(getattr(si, 'tr_cw_design_BCH', 30.0)),
                                   float(getattr(si, 'ts_cw_design_BCH', 35.0)))
        cop_sch = self._design_cop(q_sch, tr_chw, ts_chw,
                                   float(getattr(si, 'tr_cw_design_SCH', 30.0)),
                                   float(getattr(si, 'ts_cw_design_SCH', 35.0)))
        chw_b, cw_b = self._derive_flows(q_bch, cop_bch, si.delta_t_chw, si.delta_t_cw)
        chw_s, cw_s = self._derive_flows(q_sch, cop_sch, si.delta_t_chw, si.delta_t_cw)

        derived = {
            'COP_chiller_BCH': cop_bch, 'COP_chiller_SCH': cop_sch,
            'Gr_pump_chw_BCH': chw_b, 'Gr_pump_chw_SCH': chw_s,
            'Gr_pump_cw_BCH': cw_b, 'Gr_pump_cw_SCH': cw_s,
            # 冷却塔设计水流量 = 冷却泵流量
            'Gr_tower_BCH': cw_b, 'Gr_tower_SCH': cw_s,
        }
        for key, value in derived.items():
            if value is not None and hasattr(si, key):
                setattr(si, key, float(value))
        self._derived_design = dict(derived)
        return derived

    def _effective_parameters(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """返回「实际参与计算」的参数快照。

        配置里的冷机/水泵/冷却塔额定值都是**基准值**，实际值 = 基准 × 冷机容量放大系数。
        报告要求与参数快照逐项一致，所以快照必须是实际值，不能原样回显基准值，
        否则报告里会出现"额定制冷量 2112.6 kW、总装机 316,890 kW"这种自相矛盾的表。
        """
        params = dict(config or {})
        try:
            cf = float(getattr(self.station_info, 'capacity_factor', 1.0) or 1.0)
        except (TypeError, ValueError):
            cf = 1.0
        # 额定容量：基准 → 实际（× 放大系数）
        for key in ('Qr_chiller_BCH', 'Qr_chiller_SCH'):
            if key in params and isinstance(params[key], (int, float)):
                params[key] = float(params[key]) * cf
        # 加机优先级序列同样按实际容量给出（与大小机额定制冷量一致）
        qr_list = params.get('Qr_list')
        if isinstance(qr_list, list) and qr_list:
            params['Qr_list'] = [float(q) * cf for q in qr_list if isinstance(q, (int, float))]
        # 设计工况派生量（D1/D2）：以本次计算出来的为准，覆盖任何来源
        for key, value in (getattr(self, '_derived_design', None) or {}).items():
            if value is not None:
                params[key] = float(value)
        # 新结果不再有"仅展示"参数：塔设计功率与 COP 均已参与计算或为派生值
        return params

    def _tower_power_scales(self) -> Dict[str, Any]:
        """返回各通道冷却塔的设计功率归一系数（D3），供结果追溯。"""
        out: Dict[str, Any] = {}
        station = getattr(self, 'station', None)
        for name in ('channel_BCH', 'channel_SCH'):
            ch = getattr(station, name, None)
            tower = getattr(ch, 'tower', None)
            if tower is not None:
                out[name.replace('channel_', '')] = float(getattr(tower, 'k_power', 1.0))
        return out

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
        area: float = 2931000.0,
        meta: Optional[Dict[str, Any]] = None,
        result_sink: Optional[Dict[str, Any]] = None
    ) -> Iterator[Dict[str, Any]]:
        """
        流式运行仿真计算 - 每计算完一周立即 yield 结果

        result_sink（D8）：生成器结束前把本次结果写入调用方传入的字典，
        避免并发任务共享 self._last_* 而互相串号。缺省 None 时行为不变。
        """
        # ===== 更新配置 =====
        if config:
            self.update_station_config(config)
        
        if not ALGORITHM_AVAILABLE or self.station is None:
            print("⚠️ 算法不可用，使用模拟流式模式")
            yield from self._run_mock_simulation_streaming(data, area, result_sink)
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

        _display_only = provided.get('displayOnly') or []

        t_dry = [h['temp'] for h in all_hours]
        humid = [h['humid'] for h in all_hours]

        # ===== 设计裕度（D3）：总装机 ÷ 建筑负荷最大值，只读派生值 =====
        loads = [h['load'] for h in all_hours]
        peak_load = float(max(loads)) if loads else 0.0
        installed_total = float(getattr(self.station, 'Q_installed_total', 0.0) or 0.0)
        if installed_total <= 0 and self.station_info is not None:
            cf = float(getattr(self.station_info, 'capacity_factor', 1.0) or 1.0)
            installed_total = (
                self.station_info.Qr_chiller_BCH * self.station_info.n_design_BCH
                + self.station_info.Qr_chiller_SCH * self.station_info.n_design_SCH
            ) * cf
        design_margin = (installed_total / peak_load) if peak_load > 0 else None
        self._last_design_margin = design_margin
        self._last_installed_total = installed_total

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
            'caliberVersion': 'v2',
            'capacityFactor': float(getattr(self.station_info, 'capacity_factor', 1.0) or 1.0),
            'peakLoad': peak_load or None,
            'installedCapacity': installed_total or None,
            'designMargin': design_margin,
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
            # 参数快照一律由后端按实际生效值生成（D2：后端是唯一事实源），
            # 不采用调用方传入的 parameters，避免把提交的基准值当成实际值
            'parameters': self._effective_parameters(cfg),
            # 新结果不再有"仅展示"参数（D4）：COP 为派生值、塔设计功率参与计算
            'displayOnly': _display_only,
            'displayOnlyDeviations': (self._display_only_deviations(self._effective_parameters(cfg))
                                      if _display_only else {}),
            # 冷却塔设计功率的归一系数（D3），供追溯
            'towerPowerScale': self._tower_power_scales(),
        }
        self._last_summary = {
            'totalEnergy': year['totalEnergyConsumption'],
            'totalCoolingLoad': year['totalCoolingLoad'],
            'totalQStation': year['totalQStation'],
            'eui': year['totalEnergyConsumption'] / area if area > 0 else 0,
            'peakCoolingLoad': year['peakCoolingLoad'],
            'peakHeatingLoad': 0,
            'avgCop': year['avgChillerCop'],
            'avgChillerLoadRate': year['avgChillerLoadRate'],
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

        if result_sink is not None:
            result_sink.update({
                'summary': self._last_summary,
                'weekly_data': self._last_weekly_data,
                'monthly_data': self._last_monthly_data,
                'meta': self._last_meta,
                'unmet_hours_detail': self._last_unmet_hours,
            })
    
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

        # 负荷本身即为 kW，直接使用（口径 v2，不再施加量纲换算）
        load_kw = load

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
            # 当小时在线冷机的额定制冷量之和（kW），用于计算全年冷机平均负荷率
            'q_installed_active': installed,
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
            'avgChillerLoadRate': 0.0,
            'operatingStats': {}, 'loadRateHistogram': [0] * 10, 'peakContext': None,
        }
        if n == 0:
            return agg

        cop_sum = cop_cnt = 0.0
        temp_sum = 0.0
        installed_active_sum = 0.0
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
            installed_active_sum += h.get('q_installed_active', 0.0) or 0.0
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
        # 全年冷机平均负荷率 = 总供冷量 ÷ Σ(在线冷机额定制冷量 × 1h) × 100%
        agg['avgChillerLoadRate'] = (
            agg['totalQStation'] / installed_active_sum * 100.0
            if installed_active_sum > 0 else 0.0
        )
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
    
    def _run_mock_simulation_streaming(self, data: List[Dict[str, Any]], area: float = 2931000.0,
                                       result_sink: Optional[Dict[str, Any]] = None) -> Iterator[Dict[str, Any]]:
        """模拟流式仿真"""
        print("⚠️ 使用模拟流式仿真")
        
        total_p_station = 0.0
        total_load = 0.0
        total_q_station = 0.0
        peak_load = 0.0
        
        weekly: List[Dict[str, Any]] = []

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
            
            weekly.append(week_result)
            yield week_result
        
        self._last_summary = {
            'totalEnergy': total_p_station,
            'totalCoolingLoad': total_load,
            'totalQStation': total_q_station,
            'eui': total_p_station / area if area > 0 else 0,
            'peakCoolingLoad': peak_load,
            'peakHeatingLoad': 0,
            'avgCop': 3.2,
            'avgChillerLoadRate': 0.0,
            'carbonEmission': total_p_station * 0.5,
            'area': area
        }
        if result_sink is not None:
            result_sink.update({
                'summary': self._last_summary,
                'weekly_data': weekly,
                'monthly_data': [],
                'meta': {},
                'unmet_hours_detail': [],
            })


# 单例
algorithm_wrapper = AlgorithmWrapper()