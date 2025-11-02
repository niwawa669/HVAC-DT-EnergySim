import joblib
import torch
from torch import nn


class Model(nn.Module):
    def __init__(self):
        super().__init__()
        hidden_size = 1024
        self.fc1 = nn.Linear(5, hidden_size)
        self.bn1 = nn.BatchNorm1d(hidden_size)
        self.dropout = nn.Dropout(0.4739141542755807)
        self.relu1 = nn.ReLU()
        self.fc2 = nn.Linear(hidden_size, hidden_size//2)
        self.relu2 = nn.ReLU()
        self.fc3 = nn.Linear(hidden_size//2, hidden_size//4)
        self.relu3 = nn.ReLU()
        self.fc4 = nn.Linear(hidden_size//4, 1)
    
    def forward(self, x):
        x = self.fc1(x)
        x = self.bn1(x)
        x = self. dropout(x)
        x = self.relu1(x)
        x = self.fc2(x)
        x = self.relu2(x)
        x = self.fc3(x)
        x = self.relu3(x)
        x = self.fc4(x)
        return x
    

class Chiller:
    
    def __init__(self):
        self.scaler = joblib.load('./model_files/chiller/scaler.joblib')
        # 输入：'负荷率', '冷却水进水温度', '冷却水出水温度', '冷冻水回水温度', '冷冻水出水温度'，输出：'COP'
        self.model = joblib.load('./model_files/chiller/model.joblib')
        self.Qr = 2285.0
        self.load = 0
        self.tr_cw = 0
        self.ts_cw = 0
        self.tr_chw = 0
        self.ts_chw = 0
        self.COP = 0
        self.P = 0
    
    def __call__(self, load, tr_cw, ts_cw, tr_chw, ts_chw):
        self.load = load
        self.tr_cw = tr_cw
        self.ts_cw = ts_cw
        self.tr_chw = tr_chw
        self.ts_chw = ts_chw
        if load <= 0:
            self.COP = 0
            self.P = 0
        else:
            X = [[load, tr_cw, ts_cw, tr_chw, ts_chw]]
            datas = self.scaler.transform(X)
            datas = torch.tensor(datas, dtype=torch.float32)
            self.model.eval()
            with torch.no_grad():
                COP = self.model(datas)
                self.COP = COP.item()
                self.P = self.Qr * load / self.COP
        return self.COP, self.P


if __name__ == '__main__':
    
    chiller = Chiller()
    COP, P = chiller(load=1, tr_cw=30.0, ts_cw=35, tr_chw=12.0, ts_chw=7)
    print(f'COP: {COP}, P: {P}')
