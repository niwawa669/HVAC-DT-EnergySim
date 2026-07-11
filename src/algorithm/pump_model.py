import numpy as np
import torch
from device_model import *
    
    
class Pump:
    
    def __init__(self, Gr, Hr, ratio_Hz_min):
        # 输入：'流量', '扬程'  输出：'功率', '最大流量', '最小扬程', '最大扬程'
        # 'G', 'H', 'P', 'Gmax', 'Hmin', 'Hmax'
        self.Gr = Gr
        self.Hr = Hr
        self.ratio_Hz_min = ratio_Hz_min
        
        self.model = Model(2, 4, 128)
        model_file_path = './model_files/pump/model.pth'
        if os.path.exists(model_file_path):
            state_dict = torch.load(model_file_path, map_location="cpu", weights_only=False)
            self.model.load_state_dict(state_dict)
        else:
            raise FileNotFoundError("model.pth 文件不存在")
        res = self.model([[Gr, Hr]])
        self.P_r, self.Gmax_r, self.Hmin_r, self.Hmax_r = res[0]
        self.G_min = self.Gr * ratio_Hz_min
        
        self.G = 0
        self.H = 0
        self.P = 0
        self.Gmax = 0
        self.Hmin = 0
        self.Hmax = 0
    
    def __call__(self, X):
        if self.G == 0:
            self.P = 0
        else:
            datas = torch.tensor(X, dtype=torch.float32)
            res = self.model(datas)
            self.P, self.Gmax, self.Hmin, self.Hmax = res[0]
        return self.P, self.Gmax, self.Hmin, self.Hmax


if __name__ == '__main__':
    pump = Pump(
        Gr=140.0,
        Hr=14.5,
        ratio_Hz_min=30.0 / 50.0,
    )
    P, Gmax, Hmin, Hmax = pump([[140.0, 14.5]])
    print(f'P: {P}, Gmax: {Gmax}, Hmin: {Hmin}, Hmax: {Hmax}')
