import numpy as np
import torch
from device_model import *
    
    
class Pump:
    
    def __init__(self, model_file_path='model.pth'):
        # 输入：'流量', '扬程'  输出：'功率', '最大流量', '最小扬程', '最大扬程'
        # 'G', 'H', 'P', 'Gmax', 'Hmin', 'Hmax'
        self.model = Model(2, 4, 128)
        
        model_file_path = os.path.join(os.path.dirname(__file__), 'model_files/pump', model_file_path)
        if os.path.exists(model_file_path):
            state_dict = torch.load(model_file_path, map_location="cpu", weights_only=False)
            self.model.load_state_dict(state_dict)
        else:
            raise FileNotFoundError("水泵的 model.pth 文件不存在")
        
        self.Gr = 182.46
        self.Hr = 19.65
        self.ratio_Hz_min = 30.0 / 50.0
        datas = torch.tensor([[self.Gr, self.Hr]], dtype=torch.float32)
        self.P_r, self.Gmax_r, self.Hmin_r, self.Hmax_r = self.model(datas).squeeze().detach().numpy()
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
        
        datas = torch.tensor([[G, H]], dtype=torch.float32)
        self.P, self.Gmax, self.Hmin, self.Hmax = self.model(datas).squeeze().detach().numpy()
        return self.P, self.Gmax, self.Hmin, self.Hmax


if __name__ == '__main__':
    
    G_r = 182.46
    H_r = 19.65
    # P_r = 54.27663644
    # Gmax_r = 182.46
    # Hmin_r = 19.64579053
    # Hmax_r = 33.55628679
    
    G = 91.2315
    H = 32.02987907
    P = 44.64758584
    Gmax = 182.463
    Hmin = 19.64579053
    Hmax = 33.55628679

    pump = Pump()
    P, Gmax, Hmin, Hmax = pump(G, H)
    print(f'P: {P}, Gmax: {Gmax}, Hmin: {Hmin}, Hmax: {Hmax}')
