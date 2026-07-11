import numpy as np
import torch
from device_model import *


class Tower:
    
    def __init__(
        self, 
        Gw_r, 
        P_r, 
        t_dry_r=31.5, 
        t_wet_r=28.0, 
        tr_cw_r=32.0, 
        ts_cw_r=37.0, 
        tr_cw_min=20.0, 
        ratio_Hz_min=0.4, 
        coe_efficience=0.85
    ):
        # 输入：'水流量', '进风干球温度', '进风湿球温度', '进水温度', '风量', 输出：'出水温度', '风机功率'
        self.model = Model(5, 2, 128)
        model_file_path = './model_files/tower/model.pth'
        if os.path.exists(model_file_path):
            state_dict = torch.load(model_file_path, map_location="cpu", weights_only=False)
            self.model.load_state_dict(state_dict)
        else:
            raise FileNotFoundError("model.pth 文件不存在")
        
        self.Gwr = Gw_r
        self.Pr = P_r
        self.t_dry_r = t_dry_r
        self.t_wet_r = t_wet_r
        self.tr_cw_r = tr_cw_r
        self.ts_cw_r = ts_cw_r
        self.tr_cw_min = tr_cw_min
        self.ratio_Hz_min = ratio_Hz_min
        self.coe_efficience = coe_efficience
        self.Ga_r = 58910.0
        self.Ga_min = self.Ga_r * self.ratio_Hz_min
        
        self.P = 0
        self.Gw = 0
        self.t_dry = 0
        self.t_wet = 0
        self.tr_cw = 0
        self.ts_cw = 0
        self.Ga = 0
        
    def __call__(self, Gw, t_dry, t_wet, ts_cw, Ga):
        self.Gw = Gw
        self.t_dry = t_dry
        self.t_wet = t_wet
        self.ts_cw = ts_cw
        
        if Ga < self.Ga_min:
            if Ga <= 0:
                self.Ga = 0
            else:
                self.Ga = self.Ga_min
        else:
            self.Ga = Ga
        if self.Ga == 0:
            self.P = 0
            self.tr_cw = self.ts_cw
        else:
            X = [[Gw, t_dry, t_wet, ts_cw, Ga]]
            datas = torch.tensor(X, dtype=torch.float32)
            res = self.model(datas)
            self.tr_cw, self.P = res[0]
            if self.tr_cw is None:
                self.tr_cw = 0
            if self.P is None:
                self.P = 0
        return self.tr_cw, self.P / self.coe_efficience
    
    # def get_Ga_r(self, Gw, t_dry, t_wet, tr_cw, ts_cw):
    #     Ga_min = Gw * 1000.0 / 1.2
    #     delta_Ga = 1.0
    #     Ga = 0
    #     while delta_Ga > 0.01:
    #         Ga = Ga_min + delta_Ga
    #         X = [[Gw, t_dry, t_wet, ts_cw, Ga]]
    #         X = self.scaler.transform(X)
    #         datas = torch.tensor(X, dtype=torch.float32)
    #         res = self.model(datas)
    #         tr_cw_tmp, P = res[0]
    #         if P is None:
    #             raise Exception('冷却塔AI模型计算错误!')
            
    #         if tr_cw_tmp < tr_cw:
    #             Ga_min = Ga
    #         else:
    #             delta_Ga /= 2.0
    #     return Ga


if __name__ == '__main__':
    tower = Tower(
        Gw_r=166.67,
        P_r=22.0,
        t_dry_r=32.0,
        t_wet_r=28.0,
        tr_cw_r=32.0,
        ts_cw_r=37.0,
        tr_cw_min=20.0,
        ratio_Hz_min=20.0 / 50.0,
        coe_efficience=0.95,
    )
    tr_cw, P = tower(
        Gw=166.67, 
        t_dry=32.0, 
        t_wet=28.0, 
        ts_cw=37.0, 
        Ga=tower.Ga_r
    )
    print(f'tr_cw: {tr_cw}, P: {P}, Ga_r: {tower.Ga_r}')
