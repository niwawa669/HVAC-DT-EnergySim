import numpy as np
import torch
from device_model import *
    
    
class Pump:
    
    # 模型参考额定值：model.pth 训练时所对应的水泵设计点，不随选型参数变化
    Gr_ref = 182.46
    Hr_ref = 19.65
    ratio_Hz_min_ref = 30.0 / 50.0

    def __init__(self, model_file_path='model.pth', G_r=None, H_r=None, ratio_Hz_min=None):
        # 输入：'流量', '扬程'  输出：'功率', '最大流量', '最小扬程', '最大扬程'
        # 'G', 'H', 'P', 'Gmax', 'Hmin', 'Hmax'
        self.model = Model(2, 4, 128)
        
        model_file_path = os.path.join(os.path.dirname(__file__), 'model_files/pump', model_file_path)
        if os.path.exists(model_file_path):
            state_dict = torch.load(model_file_path, map_location="cpu", weights_only=False)
            self.model.load_state_dict(state_dict)
        else:
            raise FileNotFoundError("水泵的 model.pth 文件不存在")
        
        # 额定值由选型参数注入；未注入时沿用参考额定值（行为与改动前完全一致）
        self.Gr = float(self.Gr_ref if G_r is None else G_r)
        self.Hr = float(self.Hr_ref if H_r is None else H_r)
        self.ratio_Hz_min = float(self.ratio_Hz_min_ref if ratio_Hz_min is None else ratio_Hz_min)
        self.scale_applied = abs(self.Gr - self.Gr_ref) > 1e-9 or abs(self.Hr - self.Hr_ref) > 1e-9
        # ===== 相似换算（亲和定律）=====
        # 模型是在参考水泵（Gr_ref, Hr_ref）上训练的，输入为有量纲的 G、H。
        # 若选型额定值与参考值不同，必须把工作点折算到参考尺度再喂模型，
        # 再把输出折算回实际尺度，否则等于让模型在外推区间工作。
        self.kG = self.Gr / self.Gr_ref
        self.kH = self.Hr / self.Hr_ref
        # 设计点：在参考尺度下求值，折算回实际尺度即为实际额定功率
        datas = torch.tensor([[self.Gr_ref, self.Hr_ref]], dtype=torch.float32)
        P_m, Gmax_m, Hmin_m, Hmax_m = self.model(datas).squeeze().detach().numpy()
        self.P_r = float(P_m) * self.kG * self.kH
        self.Gmax_r = float(Gmax_m) * self.kG
        self.Hmin_r = float(Hmin_m) * self.kH
        self.Hmax_r = float(Hmax_m) * self.kH
        # 最小流量下限必须落在「实际尺度」上（见 D5 扩展）
        self.G_min = self.Gr * self.ratio_Hz_min
        
        self.P = 0
        self.Gmax = 0
        self.Hmin = 0
        self.Hmax = 0
    
    def __call__(self, G, H): # X = [[G, H]]
        if G == 0:
            self.P = 0
            self.Gmax = 0
            self.Hmin = 0
            self.Hmax = 0
            return self.P, self.Gmax, self.Hmin, self.Hmax
        
        # 折算到参考尺度喂模型（kG = kH = 1 时与改动前完全一致）
        datas = torch.tensor([[G / self.kG, H / self.kH]], dtype=torch.float32)
        P_m, Gmax_m, Hmin_m, Hmax_m = self.model(datas).squeeze().detach().numpy()
        # 输出折算回实际尺度：P ∝ G·H，Gmax ∝ G，Hmin/Hmax ∝ H
        self.P = float(P_m) * self.kG * self.kH
        self.Gmax = float(Gmax_m) * self.kG
        self.Hmin = float(Hmin_m) * self.kH
        self.Hmax = float(Hmax_m) * self.kH
        return self.P, self.Gmax, self.Hmin, self.Hmax


if __name__ == '__main__':
    
    G_r = 182.46
    H_r = 19.65
    # P_r = 54.27663644
    # Gmax_r = 182.46
    # Hmin_r = 19.64579053
    # Hmax_r = 33.55628679
    
    G = 155.09355
    H = 25.53823529
    P = 51.49891731
    Gmax = 182.463
    Hmin = 19.64579053
    Hmax = 33.55628679

    pump = Pump()
    P, Gmax, Hmin, Hmax = pump(G, H)
    print(f'P: {P}, Gmax: {Gmax}, Hmin: {Hmin}, Hmax: {Hmax}')
