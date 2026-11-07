import numpy as np
import torch
from device_model import *
    
    
class Pump:
    
    # 模型参考额定值：model.pth 训练时所对应的水泵设计点，不随选型参数变化
    Gr_ref = 182.46
    Hr_ref = 19.65
    ratio_Hz_min_ref = 30.0 / 50.0

    def __init__(self, model_file_path='model.pth', G_r=None, H_r=None, ratio_Hz_min=None, output_scale=1.0):
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
        # 输出尺度 = 实际设计流量 ÷ 模型参考流量（与冷机容量放大系数同源，D5）
        self.output_scale = float(output_scale or 1.0)
        # 设计点：折算到模型尺度求值，再放大回实际尺度
        datas = torch.tensor([[self.Gr / self.output_scale, self.Hr]], dtype=torch.float32)
        P_m, Gmax_m, Hmin_m, Hmax_m = self.model(datas).squeeze().detach().numpy()
        self.P_r = float(P_m) * self.output_scale
        self.Gmax_r = float(Gmax_m) * self.output_scale
        self.Hmin_r = float(Hmin_m)
        self.Hmax_r = float(Hmax_m)
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
        
        # 输入折算到模型尺度，输出放大回实际尺度；扬程是强度量，不折算
        datas = torch.tensor([[G / self.output_scale, H]], dtype=torch.float32)
        P_m, Gmax_m, Hmin_m, Hmax_m = self.model(datas).squeeze().detach().numpy()
        self.P = float(P_m) * self.output_scale
        self.Gmax = float(Gmax_m) * self.output_scale
        self.Hmin = float(Hmin_m)
        self.Hmax = float(Hmax_m)
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
