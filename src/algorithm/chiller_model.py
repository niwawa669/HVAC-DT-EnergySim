import os
import torch
from device_model import *
    

class Chiller:
    
    def __init__(self, model_file_path='model.pth'):
        # 输入：'负荷率', '冷冻水回水温度', '冷冻水出水温度', '冷却水进水温度', '冷却水出水温度'，输出：'冷机功率'
        # 'load', 'tr_chw', 'ts_chw', 'tr_cw', 'ts_cw', 'P'
        self.model = Model(5, 1, 128)
        
        model_file_path = os.path.join(os.path.dirname(__file__), 'model_files/chiller', model_file_path)
        if os.path.exists(model_file_path):
            state_dict = torch.load(model_file_path, map_location="cpu", weights_only=False)
            self.model.load_state_dict(state_dict)
        else:
            raise FileNotFoundError("冷机的 model.pth 文件不存在")
        
        self.Q_r = 2112.6  # 制冷量，单位：kW
        self.P_r = 312.83  # 制冷功率，单位：kW
        self.COP_r = 6.753

        
        self.X = None
        self.P = 0
    
    def __call__(self, load, tr_chw, ts_chw, tr_cw, ts_cw): # X = [[load, tr_chw, ts_chw, tr_cw, ts_cw]]
        if load <= 0:
            self.P = 0
            return self.P
        if load > 1.0:
            load = 1.0
        self.model.eval()
        with torch.no_grad():
            self.X = torch.tensor([[load, tr_chw, ts_chw, tr_cw, ts_cw]], dtype=torch.float32)
            self.P = self.model(self.X).squeeze().item()
        return self.P


if __name__ == '__main__':
    
    tr_cw, tr_chw, load, ts_chw, ts_cw, P = 30.0, 12.0, 0.999997388, 7.014297044, 35.04619454, 312.8334066

    chiller = Chiller()
    P = chiller(load, tr_chw, ts_chw, tr_cw, ts_cw)
    print(f'P_pred: {P}; P_label: {chiller.P_r}; COP_pred: {chiller.Q_r / P}; COP_label: {chiller.COP_r}')
