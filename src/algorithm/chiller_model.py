import numpy as np
import torch
from device_model import *
    

class Chiller:
    
    def __init__(self, Qr = 2285.0):
        # 输入：'负荷率', '冷冻水回水温度', '冷冻水出水温度', '冷却水进水温度', '冷却水出水温度'，输出：'冷机功率'
        # 'load', 'tr_chw', 'ts_chw', 'tr_cw', 'ts_cw', 'P'
        self.model = Model(5, 1, 128)
        
        model_file_path = './model_files/chiller/model.pth'
        if os.path.exists(model_file_path):
            state_dict = torch.load(model_file_path, map_location="cpu", weights_only=False)
            self.model.load_state_dict(state_dict)
        else:
            raise FileNotFoundError("model.pth 文件不存在")
        
        self.Qr = Qr
        
        self.X = np.array([[]])
        self.P = 0
    
    def __call__(self, X): # X = [[load, tr_chw, ts_chw, tr_cw, ts_cw]]
        self.X = X
        X = torch.tensor(X, dtype=torch.float32)
        X_load_0 = self.X
        self.model.eval()
        with torch.no_grad():
            self.P = self.model(X).squeeze().item()
        return self.P


if __name__ == '__main__':
    
    chiller = Chiller()
    P = chiller([[1.0, 7.0, 12.0, 30.0, 35.0]])
    print(f'P: {P}')
