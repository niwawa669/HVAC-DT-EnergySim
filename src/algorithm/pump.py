import os
import joblib
import torch
from torch import nn


class Model(nn.Module):
    def __init__(self):
        super().__init__()
        hidden_size = 128
        self.fc1 = nn.Linear(2, hidden_size)
        self.bn1 = nn.BatchNorm1d(hidden_size)
        self.dropout = nn.Dropout(0.14524069270443118)
        self.relu1 = nn.ReLU()
        self.fc2 = nn.Linear(hidden_size, hidden_size//2)
        self.relu2 = nn.ReLU()
        self.fc3 = nn.Linear(hidden_size//2, hidden_size//4)
        self.relu3 = nn.ReLU()
        self.fc4 = nn.Linear(hidden_size//4, 4)
    
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
    
    
class Pump:
    
    def __init__(self, Gr, Hr, ratio_Hz_min):
        self.scaler = joblib.load('./model_files/pump/scaler.joblib')
        # 输入：'流量', '扬程'  输出：'功率', '最大流量', '最小扬程', '最大扬程'
        self.model = joblib.load('./model_files/pump/model.joblib')
        datas = torch.tensor([[Gr, Hr]])
        res = self.model(datas)
        self.Pr, _, _, _ = res[0]
        self.Gr = Gr
        self.Hr = Hr
        self.ratio_Hz_min = ratio_Hz_min
        self.G_min = self.Gr * ratio_Hz_min
        self.G = 0
        self.H = 0
        self.P = 0
        self.Gmax = 0
        self.Hmin = 0
        self.Hmax = 0
    
    def __call__(self, G, H):
        if G < self.G_min:
            if G <= 0:
                self.G = 0
            else:
                self.G = self.G_min
        else:
            self.G = G
        self.H = H
        if self.G == 0:
            self.P = 0
        else:
            X = [[self.G, H]]
            X = self.scaler.transform(X)
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
    P, Gmax, Hmin, Hmax = pump(G=140.0, H=14.5)
    print(f'P: {P}, Gmax: {Gmax}, Hmin: {Hmin}, Hmax: {Hmax}')
