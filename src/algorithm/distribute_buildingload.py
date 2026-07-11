import pandas as pd
import numpy as np
from dataclasses import dataclass, field

from .buildingload import CsvToDataframe


@dataclass
class Config:
    file_path: str = 'buildingloads_adjusted.csv'  # 建筑冷负荷数据文件路径

    method_distribution: str = 'max'  # 按照最大释冷功率，'ratio'  # 按照释冷量与冷负荷的比例

    # 峰谷平时段设置
    peak_time: list = field(default_factory=lambda: [19,20])
    meduim_time: list = field(default_factory=lambda: [8,9,10] + [13,14,15,16,17,18] + [21])
    low_time1: list = field(default_factory=lambda: [0,1,2,3,4,5,6,7])
    low_time2: list = field(default_factory=lambda: [22,23])

    # 蓄冷释冷策略控制参数
    RTH_rate: float = 14000  # 蓄冷罐额定需冷量，RTH
    Qmax_chillers: float = 1000.0 * 3.517  # 白天，冷机供冷最大制冷量，kW
    Qmax_chillers_night: float = 1000.0 * 3.517  # 夜间， 冷机蓄冷最大制冷量，kW
    Qmax_free: float = 8200  # 白天，最大释冷功率，kW
    coe_load_limited_night: float = 1.0  # 夜间，冷机蓄冷或冷机蓄/供冷负荷限制系数

    # 全年大小月份设置
    long_month: list = field(default_factory=lambda: [1,3,5,7,8,10,12])
    short_month: list = field(default_factory=lambda: [4,6,9,11])


class DistributingLoads:

    def __init__(self, file_path, start_date, end_date):
        load_loader = CsvToDataframe(csv_path=file_path, date_column='datetime', date_format='%Y/%m/%d %H:%M')
        self.df = load_loader.filter_by_datetime(start_datetime=start_date, end_datetime=end_date)
        if self.df is None or self.df.empty:
            raise Exception('加载建筑冷负荷数据失败，请检查文件路径及数据内容是否正确.')

        # 计算仿真周期的起始时间和结束时间
        start_date = self.df.iloc[0]['datetime']
        end_date = self.df.iloc[-1]['datetime']
        self.st_month = start_date.month
        self.st_day = start_date.day
        self.ed_month = end_date.month
        self.ed_day = end_date.day
        self.year = start_date.year

        # 每天0点的剩余蓄冷量初始化
        self.RTH_end = 0

        self.config = Config()
    
    def __call__(self):
        for month in range(self.st_month, self.ed_month + 1):
            st_day = 1
            if month == self.st_month:
                st_day = self.st_day
            if month in self.config.long_month:
                ed_day = 31
                if month == self.ed_month:
                    ed_day = self.ed_day
                for day in range(st_day, ed_day + 1):
                    self.create_loads(month, day)
                    print(f'月/日：{month}/{day}，每天0点剩余蓄冷量(RTH)：{self.RTH_end}')
            elif month in self.config.short_month:
                ed_day = 30
                if month == self.ed_month:
                    ed_day = self.ed_day
                for day in range(st_day, ed_day + 1):
                    self.create_loads(month, day)
                    print(f'月/日：{month}/{day}，每天0点剩余蓄冷量(RTH)：{self.RTH_end}')
            else:
                ed_day = 28
                if month == self.ed_month:
                    ed_day = self.ed_day
                for day in range(st_day, ed_day + 1):
                    self.create_loads(month, day)
                    print(f'月/日：{month}/{day}，每天0点剩余蓄冷量(RTH)：{self.RTH_end}')
        if self.df is not None and not self.df.empty:
            self.df.to_csv('./res.csv')
            print('计算结果已保存在文件“./res.csv”中.')
        else:
            print('没有计算结果可保存.')
    
    def create_loads(self, month, day):
        loads = self.get_loads_one_day(month, day)
        sum_peak_loads = self.get_sum_loads_by_mode(loads, 'peak')
        sum_medium_loads = self.get_sum_loads_by_mode(loads, 'medium')
        loads_cheched, RTHs_residual, Qs_saved, Qs_freed = self.adjust_loads(
            loads=loads,
            sum_peak_loads=sum_peak_loads,
            sum_medium_loads=sum_medium_loads,
        )
        if self.df is None or self.df.empty:
            raise Exception('在create_loads()中，建筑冷负荷数据为空，无法保存计算结果.')
        df = self.df.loc[f'{self.year}-{month}-{day}']
        df.loc[:, '剩余蓄冷量(RTH)'] = RTHs_residual
        df.loc[:, '夜间冷机蓄冷量(kWh)'] = Qs_saved
        df.loc[:, '白天释冷量(kwH)'] = Qs_freed
        df.loc[:, '冷负荷需求校验(kWh)'] = loads_cheched

    def adjust_loads(self, loads, sum_peak_loads, sum_medium_loads):
        loads_cheched = loads.copy()
        RTHs_residual = np.array([0] * 24)
        Qs_saved = np.array([0] * 24)
        Qs_freed = np.array([0] * 24)

        # 计算峰值负荷时段的释冷量
        sum_RTHs_freed_peakloads = 0
        peak_medium_time = self.config.peak_time + self.config.meduim_time
        peak_medium_time.sort()
        for h in peak_medium_time:
            if loads[h] > self.config.Qmax_chillers:
                Q_free = loads[h] - self.config.Qmax_chillers
                if Q_free > self.config.Qmax_free:
                    Q_free = self.config.Qmax_free
                sum_RTHs_freed_peakloads += Q_free / 3.517
                Qs_freed[h] = Q_free
                loads_cheched[h] -= Q_free
                RTHs_residual[h] -= Q_free
        
        # 蓄冷、供冷、释冷负荷分配计算
        RTHs_residual[0]
        loads_cheched, RTHs_residual, Qs_saved, Qs_freed = self.adjust_loads_one_day(
            loads_cheched, RTHs_residual, Qs_saved, Qs_freed, 0, 'low1')
        RTH_residual = RTHs_residual[self.config.low_time1[-1]]  # 计算白天可以用来释冷的总的蓄冷量
        RTH_residual = self.RTH_end - sum_RTHs_freed_peakloads  # 在对峰段和平段分配蓄冷量时，需要将去掉峰值负荷消耗的蓄冷量总和
        if sum_peak_loads <= 0:
            ratio = 0
        else:
            ratio = RTH_residual / (sum_peak_loads / 3.517)
            if ratio > 1.0:
                loads_cheched, RTHs_residual, Qs_saved, Qs_freed = self.adjust_loads_one_day(
                    loads_cheched, RTHs_residual, Qs_saved, Qs_freed, 1.0, 'peak')
                RTH_residual -= sum_peak_loads / 3.517
                if sum_medium_loads <= 0:
                    ratio = 0
                else:
                    ratio = RTH_residual / (sum_medium_loads / 3.517)
                    if ratio > 1.0:
                        loads_cheched, RTHs_residual, Qs_saved, Qs_freed = self.adjust_loads_one_day(
                            loads_cheched, RTHs_residual, Qs_saved, Qs_freed, 1.0, 'medium')
                    else:
                        loads_cheched, RTHs_residual, Qs_saved, Qs_freed = self.adjust_loads_one_day(
                            loads_cheched, RTHs_residual, Qs_saved, Qs_freed, ratio, 'medium')
            else:
                loads_cheched, RTHs_residual, Qs_saved, Qs_freed = self.adjust_loads_one_day(
                    loads_cheched, RTHs_residual, Qs_saved, Qs_freed, ratio, 'peak')
                loads_cheched, RTHs_residual, Qs_saved, Qs_freed = self.adjust_loads_one_day(
                    loads_cheched, RTHs_residual, Qs_saved, Qs_freed, 0, 'medium')
        for h in peak_medium_time:
            RTHs_residual[h] += RTHs_residual[h-1]
        loads_cheched, RTHs_residual, Qs_saved, Qs_freed = self.adjust_loads_one_day(
            loads_cheched, RTHs_residual, Qs_saved, Qs_freed, 0, 'low2')
        self.RTH_end = RTHs_residual[-1]
        return loads_cheched, RTHs_residual, Qs_saved, Qs_freed

    def get_loads_one_day(self, month, day):
        loads = []
        if self.df is None or self.df.empty:
            raise Exception('在get_loads_one_day()中，建筑冷负荷数据为空，无法获取当天负荷数据.')
        df = self.df.loc[f'{self.year}-{month}-{day}']
        for load in df.loc[:, '冷负荷']:
            loads.append(load)
        return loads

    def get_sum_loads_by_mode(self, loads, mode):
        sum_loads = 0
        if mode == 'peak':
            time_list = self.config.peak_time
        elif mode == 'medium':
            time_list = self.config.meduim_time
        else:
            raise Exception('get_sum_loads_by_mode()中，mode设置错误.')
        for h in time_list:
            sum_loads += loads[h]
        return sum_loads

    def adjust_loads_one_day(self, loads_cheched, RTHs_residual, Qs_saved, Qs_freed, ratio, mode):
        if mode == 'low1' or mode == 'low2':
            loads_cheched, RTHs_residual, Qs_saved = self.ctl_Qs_saved(
                loads_cheched=loads_cheched,
                RTHs_residual=RTHs_residual,
                Qs_saved=Qs_saved,
                mode=mode
            )
        else:
            loads_cheched, RTHs_residual, Qs_freed = self.ctl_Qs_freed(
                loads_cheched=loads_cheched,
                RTHs_residual=RTHs_residual,
                Qs_freed=Qs_freed,
                ratio=ratio,
                mode=mode,
            )
        return loads_cheched, RTHs_residual, Qs_saved, Qs_freed
    
    def ctl_Qs_saved(self, loads_cheched, RTHs_residual, Qs_saved, mode):
        if mode == 'low1':
            time_list = self.config.low_time1
        elif mode == 'low2':
            time_list = self.config.low_time2
        else:
            raise Exception('在ctl_Qs_saved()中，mode设置错误.')
        for h in time_list:
            if loads_cheched[h] > self.config.Qmax_chillers_night:
                loads_cheched[h] -= self.config.Qmax_chillers_night
                Qs_saved[h] = 0
            else:
                if loads_cheched[h] > self.config.Qmax_chillers_night * self.config.coe_load_limited_night:
                    coe = 1.0
                else:
                    coe = self.config.coe_load_limited_night
                Qs_saved[h] = self.config.Qmax_chillers_night * coe - loads_cheched[h]
                loads_cheched[h] = 0
                if h == 0:
                    RTH = self.config.RTH_rate - self.RTH_end
                else:
                    RTH = self.config.RTH_rate - RTHs_residual[h-1]
                if Qs_saved[h] > RTH:
                    Qs_saved[h] = RTH
            if h == 0:
                RTHs_residual[0] = self.RTH_end + Qs_saved[0]
            else:
                RTHs_residual[h] = RTHs_residual[h-1] + Qs_saved[h]
        return loads_cheched, RTHs_residual, Qs_saved
    
    def ctl_Qs_freed(self, loads_cheched, RTHs_residual, Qs_freed, ratio, mode):
        if mode == 'peak':
            time_list = self.config.peak_time
        elif mode == 'medium':
            time_list = self.config.meduim_time
        else:
            raise Exception('ctl_Qs_freed()中，mode设置错误.')
        sum_RTHs_by_mode = 0.0
        if self.config.method_distribution == 'max':
            for h in time_list:
                sum_RTHs_by_mode += loads_cheched[h] * ratio / 3.517
        for h in time_list:
            if ratio > 0:
                if self.config.method_distribution == 'ratio':
                    Q_free = loads_cheched[h] * ratio
                elif self.config.method_distribution == 'max':
                    Q_free = loads_cheched
                else:
                    raise Exception('ctl_Qs_freed()中，method设置错误.')
                if Q_free > self.config.Qmax_free:
                    Q_free = self.config.Qmax_free
            else:
                Q_free = 0
            sum_RTHs_by_mode -= Q_free / 3.517
            if sum_RTHs_by_mode < 0:
                Q_free -= abs(sum_RTHs_by_mode) * 3.517
            Qs_freed[h] = Q_free
            RTHs_residual[h] -= Q_free / 3.517
            loads_cheched[h] -= Q_free
            if loads_cheched[h] > self.config.Qmax_chillers:
                loads_cheched[h] -= self.config.Qmax_chillers
            else:
                loads_cheched[h] = 0
        return loads_cheched, RTHs_residual, Qs_freed
