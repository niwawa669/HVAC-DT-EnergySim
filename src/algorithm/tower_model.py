import numpy as np
import torch
from device_model import *


class Tower:
    
    def __init__(self, model_file_path='model.pth'):
        # 输入：'水流量', '进风干球温度', '进风湿球温度', '进水温度', '风量', 输出：'出水温度', '风机功率'
        # ['ta_dry_in', 'da_in', 'tw_in', 'Gw', 'Ga']], df.loc[:, ['tw_out', 'P']]
        self.model = Model(5, 2, 128)
        
        model_file_path = os.path.join(os.path.dirname(__file__), 'model_files/tower', model_file_path)
        if os.path.exists(model_file_path):
            state_dict = torch.load(model_file_path, map_location="cpu", weights_only=False)
            self.model.load_state_dict(state_dict)
        else:
            raise FileNotFoundError("冷却塔的 model.pth 文件不存在")
        
        self.Gw_r = 200.0
        self.P_r = 22.0
        self.t_dry_r = 32.0
        self.da_r = 0.0225
        self.tr_cw_r = 32.0
        self.ts_cw_r = 37.0
        self.tr_cw_min = 20.0
        self.ratio_Hz_min = 20.0 / 50.0
        self.Ga_r = 58910.0
        self.Ga_min = self.Ga_r * self.ratio_Hz_min
        
        self.P = 0
        self.Gw = 0
        self.t_dry = 0
        self.da = 0
        self.tr_cw = 0
        self.ts_cw = 0
        self.Ga = 0
        
    def __call__(self, t_dry, da, ts_cw, Gw, Ga):
        self.t_dry = t_dry
        self.da = da
        self.ts_cw = ts_cw
        self.Gw = Gw
        
        if Ga < self.Ga_min:
            if Ga <= 0:
                self.Ga = 0
            else:
                self.Ga = self.Ga_min
        elif Ga > self.Ga_r:
            self.Ga = self.Ga_r
        else:
            self.Ga = Ga
        
        if self.Ga == 0:
            self.P = 0
            self.tr_cw = self.ts_cw
        else:
            datas = torch.tensor([[t_dry, da, ts_cw, Gw, Ga]], dtype=torch.float32)
            self.tr_cw, self.P = self.model(datas).squeeze().detach().numpy()
        return self.tr_cw, self.P
    
    # def get_Ga_r(self, t_dry, da, tr_cw, ts_cw, Gw):
    #     Ga_min = Gw * 1000.0 / 1.2
    #     delta_Ga = 1.0
    #     Ga = 0
    #     while delta_Ga > 0.01:
    #         Ga = Ga_min + delta_Ga
    #         datas = torch.tensor([[t_dry, da, ts_cw, Gw, Ga]], dtype=torch.float32)
    #         tr_cw_tmp, P = self.model(datas).squeeze().detach().numpy()
            
    #         if tr_cw_tmp < tr_cw:
    #             Ga_min = Ga
    #         else:
    #             delta_Ga /= 2.0
    #     return Ga


if __name__ == '__main__':
    
    tower = Tower()

    tr_cw, P = tower(
        t_dry=32.0, 
        da=0.01812, 
        ts_cw=37.0, 
        Gw=200.0, 
        Ga=tower.Ga_r
    )
    print(f'tr_cw: {tr_cw}, P: {P}, Ga_r: {tower.Ga_r}')
