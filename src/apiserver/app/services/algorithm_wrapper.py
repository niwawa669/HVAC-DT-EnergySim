"""
算法包装器 - 将您的冷站仿真算法接入 API 服务
"""
import sys
import os
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
            self.station = Station(self.station_info)
            print("✅ 冷站仿真算法初始化完成")
        except Exception as e:
            print(f"❌ 冷站初始化失败: {e}")
            self.station = None
    
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
        
        try:
            # 创建新的 StationInfo 实例
            self.station_info = StationInfo()
            
            # ===== 映射设备选型参数 =====
            # 建筑负荷
            if 'load_building_r' in config:
                self.station_info.load_building_r = config['load_building_r']
            if 'load_coe' in config:
                self.station_info.load_coe = config['load_coe']
            if 'coe' in config:
                self.station_info.coe = config['coe']
            if 'coe_tower_efficience' in config:
                self.station_info.coe_tower_efficience = config['coe_tower_efficience']
            
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
            self.station = Station(self.station_info)
            
            print("=" * 60)
            print("📋 接收到前端配置参数:")
            print(f"   建筑负荷: {config.get('load_building_r')} kW")
            print(f"   大机: {config.get('Qr_chiller_BCH')} kW × {config.get('n_design_BCH')} 台")
            print(f"   小机: {config.get('Qr_chiller_SCH')} kW × {config.get('n_design_SCH')} 台")
            print(f"   冷冻水供水温度: {config.get('ts_chw_set')} °C")
            print(f"   冷冻水供回水温差: {config.get('delta_t_chw')} °C")
            print(f"   加机负荷率: {config.get('load_up')}")
            print(f"   最小负荷率: {config.get('load_min')}")
            print("=" * 60)
            
            return True
            
        except Exception as e:
            print(f"❌ 更新冷站配置失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def run_simulation_streaming(
        self, 
        data: List[Dict[str, Any]], 
        config: Optional[Dict[str, Any]] = None,
        area: float = 2931.0
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
        
        # 查找列名
        load_col = self._find_column(df, ['load', '负荷', '冷负荷', 'cooling_load'])
        temp_col = self._find_column(df, ['t_dry', '干球温度', '温度', 'temp', 'temperature'])
        humid_col = self._find_column(df, ['d', '含湿量', '湿度', 'humidity'])
        
        if load_col is None:
            raise ValueError("未找到负荷列")
        
        print(f"检测到列: 负荷={load_col}, 温度={temp_col}, 含湿量={humid_col}")
        
        total_weeks = 52
        hours_per_week = 168
        total_energy = 0.0
        total_cooling_load = 0.0
        total_q_station = 0.0
        cop_sum = 0.0
        cop_count = 0
        peak_cooling = 0.0
        all_weekly_results = []
        all_hourly_data = []
        
        for week in range(1, total_weeks + 1):
            week_start = (week - 1) * hours_per_week
            week_end = min(week * hours_per_week, len(df))
            week_data = df.iloc[week_start:week_end]
            
            if len(week_data) == 0:
                continue
            
            week_result, hourly_loads = self._calculate_week_with_hourly(
                week_data,
                temp_col,
                humid_col,
                load_col
            )
            
            yield week_result
            
            all_weekly_results.append(week_result)
            all_hourly_data.extend(hourly_loads)
            total_energy += week_result.get('totalEnergyConsumption', 0)
            total_cooling_load += week_result.get('totalCoolingLoad', 0)
            total_q_station += week_result.get('totalQStation', 0)
            
            cop = week_result.get('avgSystemCop', 0)
            if cop > 0:
                cop_sum += cop
                cop_count += 1
            
            peak_cooling = max(peak_cooling, week_result.get('peakCoolingLoad', 0))
            
            if week % 10 == 0:
                print(f"仿真进度: {week}/{total_weeks} 周")
        
        avg_cop = cop_sum / cop_count if cop_count > 0 else 0
        self._last_summary = {
            'totalEnergy': total_energy,
            'totalCoolingLoad': total_cooling_load,
            'totalQStation': total_q_station,
            'eui': total_energy / area if area > 0 else 0,
            'peakCoolingLoad': peak_cooling,
            'peakHeatingLoad': 0,
            'avgCop': avg_cop,
            'carbonEmission': total_energy * 0.5,
            'area': area
        }
        self._last_weekly_data = all_weekly_results
        
        print(f"仿真完成: 总能耗={total_energy:.2f} kWh, 总冷负荷={total_cooling_load:.2f} kWh, 总供冷量={total_q_station:.2f} kWh")
    
    def _calculate_week_with_hourly(
        self, 
        week_data: pd.DataFrame, 
        temp_col: Optional[str], 
        humid_col: Optional[str], 
        load_col: str
    ) -> tuple:
        """计算一周的能耗，同时返回逐时数据"""
        total_load = 0.0
        peak_load = 0.0
        total_q_station = 0.0
        total_p_station = 0.0
        cop_sum = 0.0
        cop_count = 0
        outdoor_temp_sum = 0.0
        outdoor_temp_count = 0
        
        hourly_loads = []
        hourly_p_station = []
        
        for _, row in week_data.iterrows():
            load = float(row[load_col]) if pd.notna(row[load_col]) else 0
            load = max(load, 0)
            hourly_loads.append(load)
            
            if load > peak_load:
                peak_load = load
            total_load += load
            
            if temp_col and pd.notna(row[temp_col]):
                outdoor_temp = float(row[temp_col])
                outdoor_temp_sum += outdoor_temp
                outdoor_temp_count += 1
            else:
                outdoor_temp = 25
            
            if humid_col and pd.notna(row[humid_col]):
                humid = float(row[humid_col])
            else:
                humid = 0.01
            
            result = self._run_single_point(load, outdoor_temp, humid)
            
            if result:
                q_station = result.get('制冷量(kWh)', 0.0)
                chiller_power = result.get('冷机耗电量(kWh)', 0.0)
                cop = result.get('冷机COP', 0)
                pump_chw_power = result.get('冷冻泵耗电量(kWh)', 0.0)
                pump_cw_power = result.get('冷却泵耗电量(kWh)', 0.0)
                tower_power = result.get('冷却塔耗电量(kWh)', 0.0)
                
                total_q_station += q_station
                
                p_station = chiller_power + pump_chw_power + pump_cw_power + tower_power
                total_p_station += p_station
                hourly_p_station.append(p_station)
                
                if cop and cop > 0:
                    cop_sum += cop
                    cop_count += 1
                elif chiller_power > 0 and q_station > 0:
                    calculated_cop = q_station / chiller_power
                    if calculated_cop > 0:
                        cop_sum += calculated_cop
                        cop_count += 1
        
        avg_outdoor_temp = outdoor_temp_sum / outdoor_temp_count if outdoor_temp_count > 0 else 25
        week_number = int(week_data.index[0] // 168) + 1 if len(week_data) > 0 else 1
        
        avg_cop = cop_sum / cop_count if cop_count > 0 else 0
        
        print(f"📊 第 {week_number} 周: 周总负荷={total_load:.2f} kW, 周总制冷量={total_q_station:.2f} kWh, 周总能耗={total_p_station:.2f} kWh, 平均COP={avg_cop:.2f}")
        
        return {
            'weekNumber': week_number,
            'totalCoolingLoad': total_load,
            'peakCoolingLoad': peak_load,
            'totalQStation': total_q_station,
            'totalEnergyConsumption': total_p_station,
            'avgSystemCop': avg_cop,
            'avgOutdoorTemp': avg_outdoor_temp,
        }, hourly_loads
    
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