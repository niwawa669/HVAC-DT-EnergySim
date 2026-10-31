import numpy as np
import torch
from device_model import *


class Tower:
    
    # 模型参考额定值：model.pth 训练时所对应的冷却塔设计点，不随选型参数变化
    Gw_r_ref = 200.0
    P_r_ref = 22.0
    Ga_r_ref = 58910.0
    ratio_Hz_min_ref = 20.0 / 50.0

    def __init__(self, model_file_path='model.pth', Gw_r=None, P_r=None, Ga_r=None, ratio_Hz_min=None):
        # 输入：'水流量', '进风干球温度', '进风湿球温度', '进水温度', '风量', 输出：'出水温度', '风机功率'
        # ['ta_dry_in', 'da_in', 'tw_in', 'Gw', 'Ga']], df.loc[:, ['tw_out', 'P']]
        self.model = Model(5, 2, 128)
        
        model_file_path = os.path.join(os.path.dirname(__file__), 'model_files/tower', model_file_path)
        if os.path.exists(model_file_path):
            state_dict = torch.load(model_file_path, map_location="cpu", weights_only=False)
            self.model.load_state_dict(state_dict)
        else:
            raise FileNotFoundError("冷却塔的 model.pth 文件不存在")
        
        # 额定值由选型参数注入；未注入时沿用参考额定值（行为与改动前完全一致）
        self.Gw_r = float(self.Gw_r_ref if Gw_r is None else Gw_r)
        self.P_r = float(self.P_r_ref if P_r is None else P_r)
        # ===== 相似换算（亲和定律）=====
        # 模型同样是在参考冷却塔（Gw_r_ref, Ga_r_ref）上训练的，输入含水、风量两个有量纲量。
        # 气水比在同一族相似塔上不变，故风量随水量同比缩放；未显式给 Ga_r 时按此推导。
        self.kGw = self.Gw_r / self.Gw_r_ref
        self.Ga_r = float(self.Ga_r_ref * self.kGw if Ga_r is None else Ga_r)
        self.kGa = self.Ga_r / self.Ga_r_ref
        self.ratio_Hz_min = float(self.ratio_Hz_min_ref if ratio_Hz_min is None else ratio_Hz_min)
        self.scale_applied = abs(self.Gw_r - self.Gw_r_ref) > 1e-9 or abs(self.Ga_r - self.Ga_r_ref) > 1e-9
        self.t_dry_r = 32.0
        self.da_r = 0.0225
        self.tr_cw_r = 32.0
        self.ts_cw_r = 37.0
        self.tr_cw_min = 20.0
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
            # 折算到参考尺度喂模型（kGw = kGa = 1 时与改动前完全一致）
            datas = torch.tensor([[t_dry, da, ts_cw, Gw / self.kGw, self.Ga / self.kGa]], dtype=torch.float32)
            tr_m, P_m = self.model(datas).squeeze().detach().numpy()
            # 出水温度是强度量，直接透传；风机功率按尺度比折算回实际尺度
            self.tr_cw = float(tr_m)
            self.P = float(P_m) * self.kGa
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
