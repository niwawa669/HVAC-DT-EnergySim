import os, sys
from dataclasses import dataclass, field

from chiller_model import Chiller
from pump_model import Pump
from tower_model import Tower
from airH2O import *


@dataclass
class ChannelInfo:
    # 建筑暖通设计参数：load = 196572kW / 26.6, t_dry_W = 31.7, da_w = 0.02347
    load_building_r: float = 303067.16 # 建筑设计峰值负荷 kW（缺省取示例数据的峰值）（用于水力计算的分母）
    
    Qr_chiller: float = 2112.6 # 冷机实际额定冷量 kW（Station 会显式覆盖为 基准 × 放大系数）
    # ===== 各设备输出尺度（D6：每台设备按各自的模型参考点归一）=====
    # 三个模型的参考点互不相同：冷机 2112.6 kW、水泵 182.46 L/s、冷却塔 200 L/s。
    # 用同一个尺度会让设备跑到模型训练域外（历史上冷却塔因此算出负功率）。
    chiller_scale: float = 1.0   # 实际单机容量 ÷ 2112.6
    pump_chw_scale: float = 1.0  # 冷冻泵设计流量 ÷ 182.46
    pump_cw_scale: float = 1.0   # 冷却泵设计流量 ÷ 182.46
    tower_scale: float = 1.0     # 冷却塔设计水流量 ÷ 200
    n_design: int = 3 # 冷机设计台数
    tr_cw_design: float = 30.0 # 冷却水回水温度设计值
    ts_cw_design: float = 35.0 # 冷却水出水温度设计值
    tr_cw_min: float = 20.0 # 冷却回水温度最小值设置
    ta_dry_W_r: float = 31.7 # 室外干球温度设计值，标准《民用建筑供暖通风与空气调节设计规范》（GB50736-2012）值：33.2/26.4℃
    ta_wet_W_r: float = 23.47 # 室外湿球温度设计值
    load_up: float = 0.9 # 加机负荷率设置值
    load_min: float = 0.3 # 冷机最小负荷率设置值
    delta_t_chw: float = 5.0 # 冷冻水供回水温差设置值
    delta_t_cw: float = 5.0 # 冷却水供回水温差设置值
    ts_chw_set: float = 7.0 # 冷冻水供水温度设置值
    approach_set: float = 3.0 # 冷却塔逼近度设置值
    
    Hr_pt: float = 20.0 # 冷冻供回水总管扬程 mH2O
    Hr_chiller_chw: float = 6.0 # 冷机冷冻水侧设计压降 mH2O
    Hr_chiller_cw: float = 7.0 # 冷机冷却水侧设计压降 mH2O
    Hs_tower: float = 4.0 # 冷却塔设计压降 mH2O

    Gr_chiller_chw: float = 100.9 # 大机冷冻泵设计流量 L/s 92.0/32.0
    Hr_pump_chw: float = 32.0 # 大机冷冻泵设计杨程  mH2O
    n_pump_chw: int = 3 # 冷冻泵台数（D7：作为功率乘数，且不得少于同时投运的冷机台数）

    Gr_chiller_cw: float = 126.1 # 大机冷却泵设计流量 L/s 155.0/25.5
    Hr_pump_cw: float = 25.0 # 大机冷却泵设计杨程  mH2O
    n_pump_cw: int = 3 # 冷却泵台数
    
    Gr_tower: float = 200.0 # 大机冷却塔设计流量 L/s 200.0L/s / 32.0℃/23.65℃ / 36.0℃/30.44℃ / 58910m^3/h / 22kW
    Pr_tower: float = 22.0 # 大机冷却塔设计功率 kW（仅展示与标称校核，不参与功率计算）
    n_tower: int = 3 # 冷却塔台数
    
    ratio_Hz_min_pump: float = 30.0 / 50.0 # 冷却塔风机最小频率/最大频率
    ratio_Hz_min_tower:float = 20.0 / 50.0 # 冷却塔风机最小频率/最大频率
    
    
class Channel:
    
    def __init__(self, channel_info: ChannelInfo):
        self.channel_info = channel_info
        
        # 设备额定值一律由通道配置注入（单一口径：选型参数即模型额定值）。
        # 未注入的维度沿用模型的参考额定值，故默认参数下行为与改动前一致。
        self.chiller = Chiller(Q_r=channel_info.Qr_chiller,
                               output_scale=float(channel_info.chiller_scale or 1.0))
        self.pump_chw = Pump(G_r=channel_info.Gr_chiller_chw, H_r=channel_info.Hr_pump_chw,
                             output_scale=float(channel_info.pump_chw_scale or 1.0))
        self.pump_cw = Pump(G_r=channel_info.Gr_chiller_cw, H_r=channel_info.Hr_pump_cw,
                            output_scale=float(channel_info.pump_cw_scale or 1.0))
        self.tower = Tower(Gw_r=channel_info.Gr_tower, P_r=channel_info.Pr_tower,
                           output_scale=float(channel_info.tower_scale or 1.0))
        self.get_S_pipes_chw()
        self.get_S_pipes_cw()
        
        self.n_active = 0.0
        self.Q_channel = 0.0
        self.P_channel = 0.0
        self.P_chillers = 0.0
        self.P_pumps_chw = 0.0
        self.P_pumps_cw = 0.0
        self.P_towers = 0.0
        self.COP_chillers = 0.0
        self.EERs_channel = 0.0
        self.load_chiller = 0.0
        self.Gw_chw = 0.0
        self.Gw_cw = 0.0
        self.tr_cw = 0.0
        self.ts_cw = 0.0
        self.ta_dry_W = 0.0
        self.da_W = 0.0
        self.ta_wet_W = 0.0
        self.ratio_Ga_tower = 1.0
    
    def __call__(self, load, ta_dry_W, da_W, n_active):
        # 冷负荷的量纲换算由 Station 统一完成，此处保持原值（避免重复换算）
        self.ta_dry_W = ta_dry_W
        self.da_W = da_W
        self.ta_wet_W = td_b(ta_dry_W, da_W)
        self.n_active = n_active 
        
        if self.n_active <= 0:
            self.Q_channel = 0.0
            self.P_channel = 0.0
            self.P_chillers = 0.0
            self.P_pumps_chw = 0.0
            self.P_pumps_cw = 0.0
            self.P_towers = 0.0
            self.COP_chillers = 0.0
            self.EERs_channel = 0.0
            self.load_chiller = 0.0
        else:
            self.Q_channel = load
            self.load_chiller = self.Q_channel / (self.channel_info.Qr_chiller * self.n_active)
            self.ts_chw = self.channel_info.ts_chw_set
            self.tr_chw = self.ts_chw + self.channel_info.delta_t_chw
            self.Gw_chw  = self.Q_channel / 4.187 / self.channel_info.delta_t_chw
            
            self.Gw_cw = 0.0
            tr_cw_min = self.ta_wet_W
            tr_cw_tmp = 0.0
            delta_tr_cw = 1.0
            self.ratio_Ga_tower = 1.0
            while abs(delta_tr_cw) > 0.00001:
                self.tr_cw = tr_cw_min + delta_tr_cw
                if self.tr_cw < self.channel_info.tr_cw_min:
                    self.tr_cw = self.channel_info.tr_cw_min
                    self.ratio_Ga_tower = 0.25
                self.ts_cw = self.tr_cw + self.channel_info.delta_t_cw
                
                self.P_channel, self.P_chillers, self.P_pumps_chw, \
                    self.P_pumps_cw, self.P_towers, tr_cw_tmp, self.Gw_cw = \
                        self.thermal_calculation(self.tr_cw)
                
                if self.P_channel > 0:
                    self.EERs_channel = self.Q_channel / self.P_channel
                else:
                    self.EERs_channel = 0.0
                if self.P_chillers > 0:
                    self.COP_chillers = self.Q_channel / self.P_chillers
                else:
                    self.COP_chillers = 0.0

                # 计算冷却塔风量占比
                if self.tr_cw > self.channel_info.tr_cw_min:
                    approach = self.tr_cw - self.ta_wet_W
                    if approach > self.channel_info.approach_set:
                        self.ratio_Ga_tower = 1.0
                    else:
                        self.ratio_Ga_tower = approach / self.channel_info.approach_set
                else:
                    self.tr_cw = self.channel_info.tr_cw_min
                    self.ratio_Ga_tower = 0.25
                
                if tr_cw_tmp > self.tr_cw:
                    tr_cw_min = self.tr_cw
                else:
                    delta_tr_cw /= 2.0
        return self.P_channel, self.P_chillers, self.P_pumps_chw, self.P_pumps_cw, self.P_towers, self.tr_cw, self.Gw_cw
    
    def  hydraulic_calculation_chw(self, Gw_chw_chiller):
        self.H_chw_chiller = self.channel_info.Hr_chiller_chw * (Gw_chw_chiller / self.channel_info.Gr_chiller_chw)**2.0
        self.H_pt = self.channel_info.Hr_pt * (0.4 + 0.6 * self.Q_channel / self.channel_info.load_building_r)
        self.H_pump_chw = self.H_pt + self.H_chw_chiller + self.S_pipes_chw * self.Gw_chw**2.0
        return self.H_pump_chw
    
    def  hydraulic_calculation_cw(self, Gw_cw_chiller):
        self.H_cw_chiller = self.channel_info.Hr_chiller_cw * (Gw_cw_chiller / self.channel_info.Gr_chiller_cw)**2.0
        self.H_pump_cw = self.channel_info.Hs_tower + self.H_cw_chiller + self.S_pipes_cw * self.Gw_cw**2.0
        return self.H_pump_cw

    def thermal_calculation(self, tr_cw):  # 调用前，先计算self.ratio_Ga
        self.P_channel = 0.0
        self.P_chillers = 0.0
        self.P_pumps_chw = 0.0
        self.P_pumps_cw = 0.0
        self.P_towers = 0.0
        self.Gw_cw = 0.0
        if self.n_active > 0:
            # 计算单台冷机以及对应的冷冻/冷却泵和冷却塔的功率和冷却回水温度
            P_chiller = self.chiller(self.load_chiller, self.tr_chw, self.ts_chw, tr_cw, self.ts_cw)
            Q = self.chiller.Q_r * self.load_chiller
            Gw_chw_chiller = Q / 4.187 / self.channel_info.delta_t_chw
            if Gw_chw_chiller < self.pump_chw.G_min:
                Gw_chw_chiller = self.pump_chw.G_min
            self.H_pump_chw = self.hydraulic_calculation_chw(Gw_chw_chiller)
            P_pump_chw, Gw_pump_chw_max, _, _ = self.pump_chw(Gw_chw_chiller, self.H_pump_chw)
            if Gw_chw_chiller > Gw_pump_chw_max:
                Gw_chw_chiller = Gw_pump_chw_max
                self.H_pump_chw = self.hydraulic_calculation_chw(Gw_chw_chiller)
                P_pump_chw, _, _, _ = self.pump_chw(Gw_chw_chiller, self.H_pump_chw)

            Gw_cw_chiller = (Q + P_chiller) / 4.187 / self.channel_info.delta_t_cw
            if Gw_cw_chiller < self.pump_cw.G_min:
                Gw_cw_chiller = self.pump_cw.G_min
            self.H_pump_cw = self.hydraulic_calculation_cw(Gw_cw_chiller)
            P_pump_cw, Gw_pump_cw_max, _, _ = self.pump_cw(Gw_cw_chiller, self.H_pump_cw)
            if Gw_cw_chiller > Gw_pump_cw_max:
                Gw_cw_chiller = Gw_pump_cw_max
                self.H_pump_cw = self.hydraulic_calculation_cw(Gw_cw_chiller)
                P_pump_cw, _, _, _ = self.pump_cw(Gw_cw_chiller, self.H_pump_cw)
            Ga_tower = self.tower.Ga_r * self.ratio_Ga_tower
            if Ga_tower < self.tower.Ga_min:
                Ga_tower = self.tower.Ga_min
            tr_cw_tmp, P_tower = self.tower(self.ta_dry_W, self.da_W, self.ts_cw, Gw_cw_chiller, Ga_tower)
            
            # 分别计算所有在线冷机、泵和塔的功率总和，以及冷却回水温度tr_cw_tmp
            # 各设备功率按其「自身台数」累加（D7）；泵/塔台数不得少于投运冷机台数
            self.P_chillers = P_chiller * self.n_active
            self.P_pumps_chw = P_pump_chw * self.channel_info.n_pump_chw
            self.P_pumps_cw = P_pump_cw * self.channel_info.n_pump_cw
            self.P_towers = P_tower * self.channel_info.n_tower
            self.Gw_cw = Gw_cw_chiller * self.n_active
            self.P_channel = self.P_chillers + self.P_pumps_chw + self.P_pumps_cw + self.P_towers
        else:
            tr_cw_tmp = self.ts_cw
        return self.P_channel, self.P_chillers, self.P_pumps_chw, self.P_pumps_cw, self.P_towers, tr_cw_tmp, self.Gw_cw
    
    def get_S_pipes_chw(self):
        Hr_pipes_chw = self.channel_info.Hr_pump_chw - self.channel_info.Hr_chiller_chw - self.channel_info.Hr_pt
        Gr_chw = self.channel_info.Gr_chiller_chw * self.channel_info.n_design
        self.S_pipes_chw = Hr_pipes_chw / Gr_chw**2.0
    
    def get_S_pipes_cw(self):
        Hr_pipes_cw = self.channel_info.Hr_pump_cw - self.channel_info.Hr_chiller_cw - self.channel_info.Hs_tower
        Gr_cw = self.channel_info.Gr_chiller_cw * self.channel_info.n_design
        self.S_pipes_cw = Hr_pipes_cw / Gr_cw**2.0


if __name__ == '__main__':
    
    load = 303067.16
    t_dry_W = 31.7
    da_W = 0.02347
    
    channel_info = ChannelInfo()
    channel = Channel(channel_info)
    
    res = channel(load, t_dry_W, da_W, channel_info.n_design)
    
    if res is not None:
        print(f'制冷量(kWh): {channel.Q_channel:0.2f}')
        print(f'cahnnel耗电量(kWh): {res[0]:0.2f}')
        print(f'冷机耗电量(kWh): {channel.P_chillers:0.2f}')
        print(f'冷冻泵耗电量(kWh): {channel.P_pumps_chw:0.2f}')
        print(f'冷却泵耗电量(kWh): {channel.P_pumps_cw:0.2f}')
        print(f'冷却塔耗电量(kWh): {channel.P_towers:0.2f}')
        print(f'冷机COP: {res[2]:0.2f}')
        print(f'cahnnel的EERs: {res[1]:0.2f}')
    else:
        print('计算结果为空')
