import os, sys
from dataclasses import dataclass, field

from chiller_model import Chiller
from pump_model import Pump
from tower_model import Tower
from airH2O import *
from buildingload import CsvToDataframe


@dataclass
class StationInfo:
    # 建筑暖通设计参数：load = 196572kW / 26.6, t_dry_W = 31.7, da_w = 0.02347
    load_building_r: float = 196572.0 # 建筑负荷 kW
    load_coe: float = 1.0 / 26.6 # 建筑负荷修正系数
    coe: float = 1.0 / 1.2 # 系统能效修正系数
    coe_tower_efficience: float = 0.95 # 冷却塔风机效率缩放系数
    
    Qr_chiller_BCH: float = 2112.6 # 大机额定冷量 kW
    n_design_BCH: int = 3 # 大机设计台数
    tr_cw_design_BCH: float = 30.0 # 大机冷却水回水温度设计值
    ts_cw_design_BCH: float = 35.0 # 大机冷却水出水温度设计值
    Qr_chiller_SCH: float = 1056.3 # 小机额定冷量 kW
    n_design_SCH: int = 1 # 小机设计台数
    tr_cw_design_SCH: float = 30.0 # 小机冷却水回水温度设计值
    ts_cw_design_SCH: float = 35.0 # 小机冷却水出水温度设计值
    tr_cw_min: float = 20.0 # 冷却回水温度最小值设置
    ta_dry_r: float = 31.7 # 室外干球温度设计值，标准《民用建筑供暖通风与空气调节设计规范》（GB50736-2012）值：33.2/26.4℃
    ta_wet_r: float = 23.47 # 室外湿球温度设计值
    load_up: float = 0.9 # 加机负荷率设置值
    load_min: float = 0.3 # 冷机最小负荷率设置值
    Qr_list: list = field(default_factory=lambda: [1056.3, 2112.6]) # 冷机加机优先级设置
    n_design_list: list = field(default_factory=lambda: [1, 3]) # 对应Qr_list的冷机设计台数
    delta_t_chw: float = 5.0 # 冷冻水供回水温差设置值
    delta_t_cw: float = 5.0 # 冷却水供回水温差设置值
    ts_chw_set: float = 7.0 # 冷冻水供水温度设置值
    approach_set: float = 3.0 # 冷却塔逼近度设置值
    
    Hr_pt: float = 20.0 # 冷冻供回水总管扬程 mH2O
    Hr_chiller_chw_BCH: float = 6.0 # 大机冷机冷冻水侧设计压降 mH2O
    Hr_chiller_cw_BCH: float = 7.0 # 大机冷机冷却水侧设计压降 mH2O
    Hr_chiller_chw_SCH: float = 5.0 # 小机冷机冷冻水侧设计压降 mH2O
    Hr_chiller_cw_SCH: float = 6.0 # 小机冷机冷却水侧设计压降 mH2O
    Hs_tower_BCH: float = 4.0 # 大机冷却塔设计压降 mH2O
    Hs_tower_SCH: float = 3.8 # 小机冷却塔设计压降 mH2O

    Gr_pump_chw_BCH: float = 100.9 # 大机冷冻泵设计流量 L/s 92.0/32.0
    Hr_pump_chw_BCH: float = 32.0 # 大机冷冻泵设计杨程  mH2O
    Gr_pump_chw_SCH: float = 50.5 # 小机冷冻泵设计流量 L/s
    Hr_pump_chw_SCH: float = 32.0 # 小机冷冻泵设计杨程  mH2O
    
    Gr_pump_cw_BCH: float = 126.1 # 大机冷却泵设计流量 L/s 155.0/25.5
    Hr_pump_cw_BCH: float = 25.0 # 大机冷却泵设计杨程  mH2O
    Gr_pump_cw_SCH: float = 64.0 # 小机冷却泵设计流量 L/s
    Hr_pump_cw_SCH: float = 25.0 # 小机冷却泵设计杨程  mH2O
    
    Gr_tower_BCH: float = 200.0 # 大机冷却塔设计流量 L/s 200.0L/s / 32.0℃/23.65℃ / 36.0℃/30.44℃ / 58910m^3/h / 22kW
    Pr_tower_BCH: float = 22.0 # 大机冷却塔设计功率 kW
    Gr_tower_SCH: float = 100.0 # 小机冷却塔设计流量 L/s
    Pr_tower_SCH: float = 12.0 # 小机冷却塔设计功率 kW
    
    ratio_Hz_min_pump = 30.0 / 50.0 # 冷却塔风机最小频率/最大频率
    ratio_Hz_min_tower = 20.0 / 50.0 # 冷却塔风机最小频率/最大频率
    
    
class Station:
    
    def __init__(self, station_info: StationInfo):
        self.station_info = station_info
        
        self.chiller_BCH = Chiller()
        self.chiller_SCH = Chiller()
        self.pump_chw_B = Pump()
        self.pump_chw_S = Pump()
        self.pump_cw_B = Pump()
        self.pump_cw_S = Pump()
        self.tower_B = Tower()
        self.tower_S = Tower()
        self.Qr_list = self.station_info.Qr_list
        self.n_design_list = self.station_info.n_design_list
        self.channels = [
            [self.chiller_SCH, self.pump_chw_S, self.pump_cw_S, self.tower_S],
            [self.chiller_BCH, self.pump_chw_B, self.pump_cw_B, self.tower_B],
        ]
        self.get_S_pipes_chw()
        self.get_S_pipes_cw()
        
        self.n_active_list = []
        self.Q_station = 0.0
        self.P_station = 0.0
        self.P_chillers = 0.0
        self.P_pumps_chw = 0.0
        self.P_pumps_cw = 0.0
        self.P_towers = 0.0
        self.COP_chillers = 0.0
        self.EERs = 0.0
        self.load_chillers = 0.0
        self.tr_cw = 0.0
        self.ts_cw = 0.0
        self.ta_dry_W = 0.0
        self.da_W = 0.0
        self.ta_wet_W = 0.0
        self.ratio_Ga = 1.0
        self.result = None
    
    def __call__(self, load, ta_dry_W, da_W):
        load *= self.station_info.load_coe
        self.ta_dry_W = ta_dry_W
        self.da_W = da_W
        self.ta_wet_W = td_b(ta_dry_W, da_W)

        self.n_active_list = self.get_n_active_list(load)
        Qr_station = 0
        for i in range(len(self.n_design_list)):
            Qr_station += self.Qr_list[i] * self.n_design_list[i]
        
        if sum(self.n_active_list) <= 0:
            self.Q_station = 0.0
            self.P_station = 0.0
            self.P_chillers = 0.0
            self.P_pumps_chw = 0.0
            self.P_pumps_cw = 0.0
            self.P_towers = 0.0
            self.COP_chillers = 0.0
            self.EERs = 0.0
            self.load_chillers = 0.0
        else:
            self.Q_station = load
            self.load_chillers = self.Q_station / Qr_station
            self.ts_chw = self.station_info.ts_chw_set
            self.tr_chw = self.ts_chw + self.station_info.delta_t_chw
            self.Gw_chw  = self.Q_station / 4.187 / self.station_info.delta_t_chw
            
            Gw_tr_cw = 0.0
            self.Gw_cw = 0.0
            tr_cw_min = self.ta_wet_W
            tr_cw_tmp = 0.0
            delta_tr_cw = 1.0
            self.ratio_Ga = 1.0
            while abs(delta_tr_cw) > 0.00001:
                self.tr_cw = tr_cw_min + delta_tr_cw
                if self.tr_cw < self.station_info.tr_cw_min:
                    self.tr_cw = self.station_info.tr_cw_min
                    self.ratio_Ga = 0.25
                self.ts_cw = self.tr_cw + self.station_info.delta_t_cw
                
                self.P_station = 0.0
                self.P_chillers = 0.0
                self.P_pumps_chw = 0.0
                self.P_pumps_cw = 0.0
                self.P_towers = 0.0
                Gw_tr_cw = 0.0
                self.Gw_cw = 0.0
                for channel, n_active in zip(self.channels, self.n_active_list):
                    channel.append(n_active)
                    P_channel, P_chiller, P_pump_chw, P_pump_cw, P_tower, tr_cw_tmp, Gw_cw = self.channel_count(*channel)
                    self.P_station += P_channel
                    self.P_chillers += P_chiller
                    self.P_pumps_chw += P_pump_chw
                    self.P_pumps_cw += P_pump_cw
                    self.P_towers += P_tower
                    self.Gw_cw += Gw_cw
                    Gw_tr_cw += tr_cw_tmp * Gw_cw
                if self.Gw_cw > 0:
                    self.tr_cw = Gw_tr_cw / self.Gw_cw
                else:
                    self.tr_cw = self.ts_cw
                if self.P_station > 0:
                    self.EERs = self.Q_station / self.P_station
                else:
                    self.EERs = 0.0
                if self.P_chillers > 0:
                    self.COP_chillers = self.Q_station / self.P_chillers
                else:
                    self.COP_chillers = 0.0

                approach = self.tr_cw - self.ta_wet_W
                if approach > self.station_info.approach_set:
                    self.ratio_Ga = 1.0
                else:
                    if self.tr_cw > self.station_info.tr_cw_min:
                        self.ratio_Ga = approach / self.station_info.approach_set
                    else:
                        break
                
                if tr_cw_tmp > self.tr_cw:
                    tr_cw_min = self.tr_cw
                else:
                    delta_tr_cw /= 2.0
            
            self.result = {
                '冷负荷(kWh)': load,
                '制冷量(kWh)': self.Q_station,
                '冷机耗电量(kWh)': self.P_chillers,
                '冷冻泵耗电量(kWh)': self.P_pumps_chw,
                '冷却泵耗电量(kWh)': self.P_pumps_cw,
                '冷却塔耗电量(kWh)': self.P_towers,
                '冷机COP': self.COP_chillers,
                '冷站EERs': self.EERs,
            }
        return self.result
    
    def channel_count(self, chiller, pump_chw, pump_cw, tower, n_active):
        P_channel = 0.0
        P_chiller = 0.0
        P_pump_chw = 0.0
        P_pump_cw = 0.0
        P_tower = 0.0
        tr_cw = 0.0
        Gw_cw = 0.0
        if n_active > 0:
            P_chiller = chiller(self.load_chillers, self.tr_cw, self.ts_cw, self.tr_chw, self.ts_chw)
            Q = chiller.Q_r * self.load_chillers
            Gw_chw = Q / 4.187 / self.station_info.delta_t_chw
            P_pump_chw, _, _, _ = pump_chw(Gw_chw)
            Gw_cw = (Q + P_chiller) / 4.187 / self.station_info.delta_t_cw
            P_pump_cw, _, _, _ = pump_cw(Gw_cw)
            Ga = tower.Ga_r * self.ratio_Ga
            tr_cw, P_tower = tower(Gw_cw, self.ta_dry_W, self.ta_wet_W, self.tr_cw, self.ts_cw, Ga)
            P_chiller *= n_active
            P_pump_chw *= n_active
            P_pump_cw *= n_active
            P_tower *= n_active
            P_channel = P_chiller + P_pump_chw + P_pump_cw + P_tower
        else:
            tr_cw = self.ts_cw
        return P_channel, P_chiller, P_pump_chw, P_pump_cw, P_tower, tr_cw, Gw_cw
    
    def get_S_pipes_chw(self):
        Hr_pipes_chw_B = self.station_info.Hr_pump_chw_BCH - self.station_info.Hr_chiller_chw_BCH - self.station_info.Hr_pt
        Gr_chw_B = self.station_info.Gr_pump_chw_BCH * self.station_info.n_design_BCH
        self.S_pipes_chw_BCH = Hr_pipes_chw_B / Gr_chw_B**2.0
        
        Hr_pipes_chw_S = self.station_info.Hr_pump_chw_SCH - self.station_info.Hr_chiller_chw_SCH - self.station_info.Hr_pt
        Gr_chw_S = self.station_info.Gr_pump_chw_SCH * self.station_info.n_design_SCH
        self.S_pipes_chw_SCH = Hr_pipes_chw_S / Gr_chw_S**2.0
    
    def get_S_pipes_cw(self):
        Hr_pipes_cw_B = self.station_info.Hr_pump_cw_BCH - self.station_info.Hr_chiller_cw_BCH - self.station_info.Hs_tower_BCH
        Gr_cw_B = self.station_info.Gr_pump_cw_BCH * self.station_info.n_design_BCH
        self.S_pipes_cw_BCH = Hr_pipes_cw_B / Gr_cw_B**2.0
        
        Hr_pipes_cw_S = self.station_info.Hr_pump_cw_SCH - self.station_info.Hr_chiller_cw_SCH - self.station_info.Hs_tower_SCH
        Gr_cw_S = self.station_info.Gr_pump_cw_SCH * self.station_info.n_design_SCH
        self.S_pipes_cw_SCH = Hr_pipes_cw_S / Gr_cw_S**2.0
    
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
        Qr_active = 0.0
        for i in range(len(n_active_list)):
            Qr_active += self.Qr_list[i] * n_active_list[i]
        return Qr_active * self.station_info.load_up


if __name__ == '__main__':
    
    load = 196572.0
    t_dry_W = 31.7
    da_W = 0.02347
    
    station_info = StationInfo()
    station = Station(station_info)
    
    res = station(load, t_dry_W, da_W)
    
    if res is not None:
        print(f'冷负荷(kWh): {res["冷负荷(kWh)"]}')
        print(f'制冷量(kWh): {res["制冷量(kWh)"]}')
        print(f'冷机耗电量(kWh): {res["冷机耗电量(kWh)"]}')
        print(f'冷冻泵耗电量(kWh): {res["冷冻泵耗电量(kWh)"]}')
        print(f'冷却泵耗电量(kWh): {res["冷却泵耗电量(kWh)"]}')
        print(f'冷却塔耗电量(kWh): {res["冷却塔耗电量(kWh)"]}')
        print(f'冷机COP: {res["冷机COP"]}')
        print(f'冷站EERs: {res["冷站EERs"]}')
    else:
        print('计算结果为空')
