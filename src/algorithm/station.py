import numpy as np
import pandas as pd
from dataclasses import dataclass, field

from .chiller import Chiller
from .pump import Pump
from .tower import Tower
from .read_datas import read_buildingload_datas


@dataclass
class StationInfo:
    coe: float = 1.0 / 1.2 # 系统能效修正系数
    coe_tower_efficience: float = 0.95 # 冷却塔风机效率缩放系数
    
    Qr_chiller_BCH: float = 738.0 # 大机额定冷量 kW
    n_design_BCH: int = 1 # 大机设计台数
    tr_cw_design_BCH: float = 32.0 # 大机冷却水回水温度设计值
    ts_cw_design_BCH: float = 37.0 # 大机冷却水出水温度设计值
    Qr_chiller_SCH: float = 402.7 # 小机额定冷量 kW
    n_design_SCH: int = 1 # 小机设计台数
    tr_cw_design_SCH: float = 32.0 # 小机冷却水回水温度设计值
    ts_cw_design_SCH: float = 37.0 # 小机冷却水出水温度设计值
    tr_cw_min: float = 20.0 # 冷却回水温度最小值设置
    ta_dry_r: float = 20.0 # 室外干球温度设计值
    ta_wet_r: float = 20.0 # 室外湿球温度设计值
    load_loadup: float = 0.9 # 加机负荷率设置值
    load_min: float = 0.3 # 冷机最小负荷率设置值
    Qr_list: list = field(default_factory=lambda: [402.7, 738.0]) # 冷机加机优先级设置
    n_design_list: list = field(default_factory=lambda: [1, 1]) # 对应Qr_list的冷机设计台数
    delta_t_chw: float = 5.0 # 冷冻水供回水温差设置值
    delta_t_cw: float = 5.0 # 冷却水供回水温差设置值
    ts_chw_set: float = 7.0 # 冷冻水供水温度设置值
    approach_set: float = 3.0 # 冷却塔逼近度设置值
    
    Gr_pump_chw_BCH: float = 140.0 # 大机冷冻泵设计流量
    Hr_pump_chw_BCH: float = 14.5 # 大机冷冻泵设计功率  修正
    Gr_pump_chw_SCH: float = 65.0 # 小机冷冻泵设计流量
    Hr_pump_chw_SCH: float = 7.7 # 小机冷冻泵设计功率
    
    Gr_pump_cw_BCH: float = 140.0 # 大机冷却泵设计流量
    Hr_pump_cw_BCH: float = 14.5 # 大机冷却泵设计功率  修正
    Gr_pump_cw_SCH: float = 65.0 # 小机冷却泵设计流量
    Hr_pump_cw_SCH: float = 7.7 # 小机冷却泵设计功率
    
    Gr_tower_BCH: float = 140.0 # 大机冷却塔设计流量
    Pr_tower_BCH: float = 14.5 # 大机冷却塔设计功率
    Gr_tower_SCH: float = 65.0 # 小机冷却塔设计流量
    Pr_tower_SCH: float = 7.7 # 小机冷却塔设计功率
    approach_set: float = 3.0 # 冷却塔逼近度设置值
    
    ratio_Hz_min_pump = 30.0 / 50.0 # 冷却塔风机最小频率/最大频率
    ratio_Hz_min_tower = 20.0 / 50.0 # 冷却塔风机最小频率/最大频率
    
    
class Station:
    
    def __init__(self, station_info: StationInfo):
        self.station_info = station_info
        
        self.chiller_BCH = Chiller()
        self.chiller_SCH = Chiller()
        self.pump_chw_B = Pump(
            Gr=self.station_info.Gr_pump_chw_BCH,
            Hr=self.station_info.Hr_pump_chw_BCH,
            ratio_Hz_min=self.station_info.ratio_Hz_min_pump,
        )
        self.pump_chw_S = Pump(
            Gr=self.station_info.Gr_pump_chw_SCH,
            Hr=self.station_info.Hr_pump_chw_SCH,
            ratio_Hz_min=self.station_info.ratio_Hz_min_pump,
        )
        self.pump_cw_B = Pump(
            Gr=self.station_info.Gr_pump_cw_BCH,
            Hr=self.station_info.Hr_pump_cw_BCH,
            ratio_Hz_min=self.station_info.ratio_Hz_min_pump,
        )
        self.pump_cw_S = Pump(
            Gr=self.station_info.Gr_pump_cw_SCH,
            Hr=self.station_info.Hr_pump_cw_SCH,
            ratio_Hz_min=self.station_info.ratio_Hz_min_pump,
        )
        self.tower_B = Tower(
            Gwr=self.station_info.Gr_tower_BCH,
            Pr=self.station_info.Pr_tower_BCH,
            t_dry_r=self.station_info.ta_dry_r,
            t_wet_r=self.station_info.ta_wet_r,
            tr_cw_r=self.station_info.tr_cw_design_BCH,
            ts_cw_r=self.station_info.ts_cw_design_BCH,
            tr_cw_min=self.station_info.tr_cw_min,
            ratio_Hz_min=self.station_info.ratio_Hz_min_tower,
            coe_efficience=self.station_info.coe_tower_efficience,
        )
        self.tower_S = Tower(
            Gwr=self.station_info.Gr_tower_SCH,
            Pr=self.station_info.Pr_tower_SCH,
            t_dry_r=self.station_info.ta_dry_r,
            t_wet_r=self.station_info.ta_wet_r,
            tr_cw_r=self.station_info.tr_cw_design_SCH,
            ts_cw_r=self.station_info.ts_cw_design_SCH,
            tr_cw_min=self.station_info.tr_cw_min,
            ratio_Hz_min=self.station_info.ratio_Hz_min_tower,
            coe_efficience=self.station_info.coe_tower_efficience,
        )
        self.Qr_list = self.station_info.Qr_list
        self.n_design_list = self.station_info.n_design_list
        self.channels = [
            [self.chiller_SCH, self.pump_chw_S, self.pump_cw_S, self.tower_S],
            [self.chiller_BCH, self.pump_chw_B, self.pump_cw_B, self.tower_B],
        ]
        self.n_active_list = []
        self.Q = 0
        self.P = 0
        self.P_chillers = 0
        self.P_pumps_chw = 0
        self.P_pumps_cw = 0
        self.P_towers = 0
        self.COP_chillers = 0
        self.EERs = 0
        self.load_chillers = 0
        self.tr_cw = None
        self.ts_cw = None
        self.ta_dry = None
        self.ta_wet = None
        self.ratio_Ga = 1.0
        self.res = None
    
    def __call__(self, load, ta_dry, ta_wet):
        self.ta_dry = ta_dry
        self.ta_wet = ta_wet
        self.n_active_list = self.get_n_active_list(load)
        Qr_station = 0
        for i in range(len(self.n_design_list)):
            Qr_station += self.Qr_list[i] * self.n_design_list[i]
        if sum(self.n_active_list) <= 0:
            self.Q = 0
            self.P = 0
            self.P_chillers = 0
            self.P_pumps_chw = 0
            self.P_pumps_cw = 0
            self.P_towers = 0
            self.COP_chillers = 0
            self.EERs = 0
            self.load_chillers = 0
        else:
            self.Q = load
            self.load_chillers = self.Q / Qr_station
            self.ts_chw = self.station_info.ts_chw_set
            self.tr_chw = self.ts_chw + self.station_info.delta_t_chw
            self.P = 0
            self.P_chillers = 0
            self.P_pumps_chw = 0
            self.P_pumps_cw = 0
            self.P_towers = 0
            self.tr_cw = ta_wet
            self.ts_cw = self.tr_cw + self.station_info.delta_t_cw
            delta_approach = 1.0
            delta_approach_pre = 0
            self.ratio_Ga = 1.0
            while abs(delta_approach) > 0.001:
                self.tr_cw -= delta_approach
                self.ts_cw = self.tr_cw + self.station_info.delta_t_cw
                Gw_tr_cw = 0
                Gw_cw = 0
                tr_cw_c = 0
                for channel, n_active in zip(self.channels, self.n_active_list):
                    channel.append(n_active)
                    P_channel, P_chiller, P_pump_chw, P_pump_cw, P_tower, tr_cw_c, Gw_cw_c = self.channel_count(*channel)
                    self.P += P_channel
                    self.P_chillers += P_chiller
                    self.P_pumps_chw += P_pump_chw
                    self.P_pumps_cw += P_pump_cw
                    self.P_towers += P_tower
                    Gw_cw += Gw_cw_c
                    if tr_cw_c is None:
                        tr_cw_c = 0
                    Gw_tr_cw += tr_cw_c * Gw_cw_c
                if Gw_cw > 0:
                    self.tr_cw = Gw_tr_cw / Gw_cw
                else:
                    self.tr_cw = self.ts_cw
                if self.P > 0:
                    self.EERs = self.Q / self.P
                else:
                    self.EERs = 0
                if self.P_chillers > 0:
                    self.COP_chillers = self.Q / self.P_chillers
                else:
                    self.COP_chillers = 0
                
                approach = self.tr_cw - self.ta_wet
                delta_approach = approach - self.station_info.approach_set
                if abs(delta_approach - delta_approach_pre) < 0.0001:
                    break
                delta_approach_pre = delta_approach
                
                if self.tr_cw - self.station_info.tr_cw_min < 0.001:
                    if self.tr_cw - self.station_info.tr_cw_min > 0:
                        break
                    else:
                        self.ratio_Ga = 1.0 - (self.station_info.tr_cw_min - self.tr_cw) / self.tr_cw
                        continue
                else:
                    self.ratio_Ga = 1.0 + delta_approach / approach
            
            self.res = {
                '冷负荷(kWh)': load,
                '制冷量(kWh)': self.Q,
                '冷机耗电量(kWh)': self.P_chillers,
                '冷冻泵耗电量(kWh)': self.P_pumps_chw,
                '冷却泵耗电量(kWh)': self.P_pumps_cw,
                '冷却塔耗电量(kWh)': self.P_towers,
                '冷机COP': self.COP_chillers,
                '冷站EERs': self.EERs,
            }
        return self.res
    
    def channel_count(self, chiller, pump_chw, pump_cw, tower, n_active):
        P_channel = 0
        P_chiller = 0
        P_pump_chw = 0
        P_pump_cw = 0
        P_tower = 0
        tr_cw = 0
        Gw_cw = 0
        if n_active > 0:
            _, P_chiller = chiller(self.load_chillers, self.tr_cw, self.ts_cw, self.tr_chw, self.ts_chw)
            Q = chiller.Qr * self.load_chillers
            Gw_chw = Q / 4.187 / self.station_info.delta_t_chw
            P_pump_chw = pump_chw(Gw_chw)
            Gw_cw = (Q + P_chiller) / 4.187 / self.station_info.delta_t_cw
            P_pump_cw = pump_cw(Gw_cw)
            Ga = tower.Gar * self.ratio_Ga
            tr_cw, P_tower = tower(Gw_cw, self.ta_dry, self.ta_wet, self.tr_cw, self.ts_cw, Ga)
            P_chiller *= n_active
            P_pump_chw *= n_active
            P_pump_cw *= n_active
            P_tower *= n_active
            P_channel = P_chiller + P_pump_chw + P_pump_cw + P_tower
        else:
            tr_cw = self.ts_cw
        return P_channel, P_chiller, P_pump_chw, P_pump_cw, P_tower, tr_cw, Gw_cw
    
    def get_n_active_list(self, load):
        num = len(self.n_design_list)
        
        if load < min(self.Qr_list) * self.station_info.load_min:
            self.n_active_list = [0] * num
            return self.n_active_list
        
        self.n_active_list = self.n_design_list.copy()
        for i in range(num):
            while self.n_active_list[num-i-1] > 0:
                self.n_active_list[num-i-1] -= 1
                Qr_active = self.get_Qr_active(self.n_active_list)
                if load > Qr_active:
                    self.n_active_list[num-i-1] += 1
                    break
        return self.n_active_list
    
    def get_Qr_active(self, n_active_list):
        Qr_active = 0
        for i in range(len(n_active_list)):
            Qr_active += self.Qr_list[i] * n_active_list[i]
        return Qr_active * self.station_info.load_loadup
    