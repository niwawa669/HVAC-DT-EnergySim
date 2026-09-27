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
        
        if Station is not None and StationInfo is not None:
            self.station_info = StationInfo()
            self.station = Station(self.station_info)
            print("✅ 冷站仿真算法初始化完成")
        else:
            print(f"❌ 冷站初始化失败: {e}")
            self.station = None
    
    def run_simulation_streaming(
        self, 
        data: List[Dict[str, Any]], 
        config: Optional[Dict[str, Any]] = None,
        area: float = 2931.0
    ) -> Iterator[Dict[str, Any]]:
        """
        流式运行仿真计算 - 每计算完一周立即 yield 结果
        """
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
            
            # 计算本周
            week_result, hourly_loads = self._calculate_week_with_hourly(
                week_data,
                temp_col,
                humid_col,
                load_col
            )
            
            # 立即 yield 本周结果
            yield week_result
            
            # 累积汇总数据
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
        
        # 保存汇总结果
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
        total_Q_station = 0.0
        total_P_station = 0.0
        cop_sum = 0.0
        cop_count = 0
        OutdoorTemp_sum = 0.0
        OutdoorTemp_count = 0
        
        hourly_loads = []
        hourly_Ps_station = []
        
        for _, row in week_data.iterrows():
            load = float(row[load_col]) if pd.notna(row[load_col]) else 0
            load = max(load, 0)
            hourly_loads.append(load)
            if load > peak_load:
                peak_load = load
            total_load += load
            
            if temp_col and pd.notna(row[temp_col]):
                OutdoorTemp = float(row[temp_col])
                OutdoorTemp_sum += OutdoorTemp
                OutdoorTemp_count += 1
            else:
                OutdoorTemp = 25
            
            if humid_col and pd.notna(row[humid_col]):
                humid = float(row[humid_col])
            else:
                humid = 0.01
            
            result = self._run_single_point(load, OutdoorTemp, humid)
            
            '''
            self.result = {
                            '冷负荷(kWh)': load_building,
                            '制冷量(kWh)': self.Q_station,
                            '冷机耗电量(kWh)': self.P_chillers,
                            '冷冻泵耗电量(kWh)': self.P_pumps_chw,
                            '冷却泵耗电量(kWh)': self.P_pumps_cw,
                            '冷却塔耗电量(kWh)': self.P_towers,
                            '冷机COP': self.COP_chillers,
                            '冷站EERs': self.EERs,
                        }
            '''
            if result:
                Q_station = result.get('制冷量(kWh)', 0.0)
                chiller_power = result.get('冷机耗电量(kWh)', 0.0)
                cop = result.get('冷机COP', 0)
                pump_chw_power = result.get('冷冻泵耗电量(kWh)', 0.0)
                pump_cw_power = result.get('冷却泵耗电量(kWh)', 0.0)
                tower_power = result.get('冷却塔耗电量(kWh)', 0.0)
                
                total_Q_station += Q_station
                
                p_station = chiller_power + pump_chw_power + pump_cw_power + tower_power
                total_P_station += p_station
                hourly_Ps_station.append(p_station)
                
                if cop and cop > 0:
                    cop_sum += cop
                    cop_count += 1
                elif chiller_power > 0 and Q_station > 0:
                    cop_sum = Q_station / chiller_power
                    cop_count += 1
        
        avgOutdoorTemp = OutdoorTemp_sum / OutdoorTemp_count if OutdoorTemp_count > 0 else 25
        week_number = int(week_data.index[0] // 168) + 1 if len(week_data) > 0 else 1
        
        avg_cop = cop_sum / cop_count if cop_count > 0 else 0
        
        print(f"📊 第 {week_number} 周: 周总负荷={total_load:.2f} kW, 周总制冷量={total_Q_station} kW, 周总能耗={total_P_station:.2f} kWh, 平均COP={avg_cop:.2f}")
        
        return {
            'weekNumber': week_number,
            'totalCoolingLoad': total_load,
            'peakCoolingLoad': peak_load,
            'totalQStation': total_Q_station,
            'totalEnergyConsumption': total_P_station,
            'avgSystemCop': avg_cop,
            'avgOutdoorTemp': avgOutdoorTemp,
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
        
        total_P_station = 0.0
        total_load = 0.0
        peak_load = 0.0
        
        for week in range(1, 53):
            week_P_station = 1500 + random.uniform(0, 1500)
            cooling_load = 200 + random.uniform(0, 300)
            week_temp = 15 + 10 * math.sin((week / 52) * 2 * math.pi) + random.uniform(-2, 2)
            
            week_result = {
                'weekNumber': week,
                'totalCoolingLoad': cooling_load * 168,
                'peakCoolingLoad': cooling_load,
                'totalQStation': cooling_load * 168,
                'totalEnergyConsumption': week_P_station,
                'avgSystemCop': 3.0 + random.uniform(0, 0.5),
                'avgOutdoorTemp': week_temp,
            }
            
            total_P_station += week_P_station
            total_load += cooling_load * 168
            if cooling_load > peak_load:
                peak_load = cooling_load
            
            yield week_result
        
        self._last_summary = {
            'totalEnergy': total_P_station,
            'totalCoolingLoad': total_load,
            'eui': total_P_station / area if area > 0 else 0,
            'peakCoolingLoad': peak_load,
            'peakHeatingLoad': 0,
            'avgCop': 3.2,
            'carbonEmission': total_P_station * 0.5,
            'area': area
        }


# 单例
algorithm_wrapper = AlgorithmWrapper()