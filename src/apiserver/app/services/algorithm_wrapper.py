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
        self._initialize_station()
    
    def _initialize_station(self):
        """初始化冷站配置"""
        if not ALGORITHM_AVAILABLE or StationInfo is None:
            print("⚠️ 算法不可用，使用模拟模式")
            return
        
        if StationInfo is not None and Station is not None:
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
        
        Yields:
            每周的仿真结果字典
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
        
        print(f"检测到列: 负荷={load_col}, 温度={temp_col}, 含湿量={humid_col}")
        
        total_weeks = 52
        hours_per_week = 168
        total_energy = 0.0
        cop_sum = 0.0
        cop_count = 0
        peak_cooling = 0.0
        all_weekly_results = []
        
        for week in range(1, total_weeks + 1):
            week_start = (week - 1) * hours_per_week
            week_end = min(week * hours_per_week, len(df))
            week_data = df.iloc[week_start:week_end]
            
            if len(week_data) == 0:
                continue
            
            # ===== 计算本周 =====
            week_result = self._calculate_week(
                week_data,
                temp_col,
                humid_col,
                load_col
            )
            
            # ===== 立即 yield 本周结果（流式推送） =====
            yield week_result
            
            # 累积汇总数据
            all_weekly_results.append(week_result)
            total_energy += week_result.get('totalEnergyConsumption', 0)
            
            cop = week_result.get('avgSystemCop', 0)
            if cop > 0:
                cop_sum += cop
                cop_count += 1
            
            peak_cooling = max(peak_cooling, week_result.get('peakCoolingLoad', 0))
            
            if week % 10 == 0:
                print(f"仿真进度: {week}/{total_weeks} 周")
        
        # 保存汇总结果到实例变量，供后续使用
        avg_cop = cop_sum / cop_count if cop_count > 0 else 0
        self._last_summary = {
            'totalEnergy': total_energy,
            'eui': total_energy / area if area > 0 else 0,
            'peakCoolingLoad': peak_cooling,
            'peakHeatingLoad': 0,
            'avgCop': avg_cop,
            'carbonEmission': total_energy * 0.5
        }
        self._last_weekly_data = all_weekly_results
        
        print(f"仿真完成: 总能耗={total_energy:.2f} kWh")
    
    def get_last_summary(self) -> Dict[str, Any]:
        """获取最后一次仿真的汇总结果"""
        return getattr(self, '_last_summary', {
            'totalEnergy': 0,
            'eui': 0,
            'peakCoolingLoad': 0,
            'peakHeatingLoad': 0,
            'avgCop': 0,
            'carbonEmission': 0
        })
    
    def get_last_weekly_data(self) -> List[Dict[str, Any]]:
        """获取最后一次仿真的周度数据"""
        return getattr(self, '_last_weekly_data', [])
    
    def _calculate_week(
        self, 
        week_data: pd.DataFrame, 
        temp_col: Optional[str], 
        humid_col: Optional[str], 
        load_col: str
    ) -> Dict[str, Any]:
        """计算一周的能耗"""
        total_cooling_load = 0.0
        total_energy = 0.0
        cop_sum = 0.0
        cop_count = 0
        peak_cooling = 0.0
        temp_sum = 0.0
        temp_count = 0
        
        for _, row in week_data.iterrows():
            load = float(row[load_col]) if pd.notna(row[load_col]) else 0
            
            if temp_col and pd.notna(row[temp_col]):
                temp = float(row[temp_col])
                temp_sum += temp
                temp_count += 1
            else:
                temp = 25
            
            if humid_col and pd.notna(row[humid_col]):
                humid = float(row[humid_col])
            else:
                humid = 0.01
            
            cooling_load = max(load, 0)
            
            # 运行单点仿真
            result = self._run_single_point(abs(load), temp, humid)
            
            total_cooling_load += cooling_load
            
            if result:
                # 获取单点能耗
                # 冷站总耗电 = 冷机耗电 + 冷冻泵耗电 + 冷却泵耗电 + 冷却塔耗电
                chiller_power = result.get('冷机耗电量(kWh)', 0)
                pump_chw_power = result.get('冷冻泵耗电量(kWh)', 0)
                pump_cw_power = result.get('冷却泵耗电量(kWh)', 0)
                tower_power = result.get('冷却塔耗电量(kWh)', 0)
                
                # 确保耗电量为正数（如果为负数，取绝对值或设为0）
                pump_cw_power = abs(pump_cw_power) if pump_cw_power < 0 else pump_cw_power
                tower_power = abs(tower_power) if tower_power < 0 else tower_power
                
                # 总能耗
                p_station = chiller_power + pump_chw_power + pump_cw_power + tower_power
                total_energy += p_station
                
                # 从算法结果中获取 COP
                cop = result.get('冷机COP', 0)
                if cop and cop > 0:
                    cop_sum += cop
                    cop_count += 1
                else:
                    # 如果算法没有返回 COP，从能耗推算
                    if chiller_power > 0 and cooling_load > 0:
                        calculated_cop = cooling_load / chiller_power
                        if calculated_cop > 0:
                            cop_sum += calculated_cop
                            cop_count += 1
                
                if cooling_load > peak_cooling:
                    peak_cooling = cooling_load
        
        avg_temp = temp_sum / temp_count if temp_count > 0 else 25
        week_number = int(week_data.index[0] // 168) + 1 if len(week_data) > 0 else 1
        
        # 计算平均 COP
        avg_cop = cop_sum / cop_count if cop_count > 0 else 0
        
        # ===== 打印调试日志 =====
        print(f"📊 第 {week_number} 周: 能耗={total_energy:.2f} kWh, 负荷={total_cooling_load:.2f} kW, COP={avg_cop:.2f} (样本数: {cop_count})")
        
        return {
            'weekNumber': week_number,
            'avgOutdoorTemp': avg_temp,
            'totalCoolingLoad': total_cooling_load,
            'totalHeatingLoad': 0,
            'totalEnergyConsumption': total_energy,
            'avgSystemCop': cop_sum / cop_count if cop_count > 0 else 0,
            'peakCoolingLoad': peak_cooling,
            'peakHeatingLoad': 0
        }
    
    def _run_single_point(self, load: float, temp: float, humid: float) -> Optional[Dict[str, Any]]:
        """运行单点仿真"""
        if self.station is None:
            return None
        
        try:
            result = self.station(load, temp, humid)
            if result:
                # 确保 COP 字段存在
                if '冷机COP' not in result and 'COP_chillers' in result:
                    result['冷机COP'] = result['COP_chillers']
                elif '冷机COP' not in result and 'cop' in result:
                    result['冷机COP'] = result['cop']
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
    
    def _run_mock_simulation_streaming(self, data: List[Dict[str, Any]], area: float = 2931.0) -> Iterator[Dict[str, Any]]:
        """模拟流式仿真"""
        print("⚠️ 使用模拟流式仿真")
        
        total_energy = 0.0
        peak_cooling = 0.0
        
        for week in range(1, 53):
            week_energy = 1500 + random.uniform(0, 1500)
            cooling_load = 200 + random.uniform(0, 300)
            week_temp = 15 + 10 * math.sin((week / 52) * 2 * math.pi) + random.uniform(-2, 2)
            
            week_result = {
                'weekNumber': week,
                'avgOutdoorTemp': week_temp,
                'totalCoolingLoad': cooling_load * 168,
                'totalHeatingLoad': 0,
                'totalEnergyConsumption': week_energy,
                'avgSystemCop': 3.0 + random.uniform(0, 0.5),
                'peakCoolingLoad': cooling_load,
                'peakHeatingLoad': 0
            }
            
            total_energy += week_energy
            if cooling_load > peak_cooling:
                peak_cooling = cooling_load
            
            # ===== 立即 yield =====
            yield week_result
        
        # 保存汇总
        self._last_summary = {
            'totalEnergy': total_energy,
            'eui': total_energy / area if area > 0 else 0,
            'peakCoolingLoad': peak_cooling,
            'peakHeatingLoad': 0,
            'avgCop': 3.2,
            'carbonEmission': total_energy * 0.5
        }


# 单例
algorithm_wrapper = AlgorithmWrapper()