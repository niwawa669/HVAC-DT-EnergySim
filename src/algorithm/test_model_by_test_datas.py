import os
import numpy as np
import pandas as pd
import torch
from torch import nn
from sklearn.preprocessing import StandardScaler


input_size = 5
output_size = 2
hidden_size = 128
model_file_path = './best_tower_model/model.pth'

class WhiteningLayer(nn.Module):
    def __init__(self, input_size):
        super().__init__()
        self.register_buffer('mean', torch.zeros(input_size))
        self.register_buffer('std', torch.ones(input_size))
        self.register_buffer('W', torch.eye(input_size))
    
    def fit(self, data: torch.Tensor):
        mean = data.mean(dim=0)
        std = data.std(dim=0)
        data = (data - mean) / std
        cov = data.T @ data / (data.size(0) - 1.0)
        U, S, V = torch.svd(cov)
        inv_S = torch.diag(1.0 / torch.sqrt(S + 1.0e-10))
        self.W = U @ inv_S @ U.T
        self.mean.data = mean
        self.std.data = std
    
    def forward(self, x: torch.Tensor):
        if x.dim() == 1:
            x = x.unsqueeze(0)
        x = (x - self.mean) / self.std # type: ignore
        return x @ self.W

class Model(nn.Module):
    def __init__(self, input_size, output_size, hidden_size):
        super().__init__()
        self.whitening = WhiteningLayer(input_size)
        self.fc1 = nn.Linear(input_size, hidden_size)
        self.fc2 = nn.Linear(hidden_size, hidden_size//2)
        self.fc3 = nn.Linear(hidden_size//2, output_size)
        self.relu = nn.ReLU()
    
    def forward(self, x: torch.Tensor):
        self.whitening(x)
        x = self.fc1(x)
        x = self.relu(x)
        x = self.fc2(x)
        x = self.relu(x)
        x = self.fc3(x)
        return x

model = Model(input_size, output_size, hidden_size)
if os.path.exists(model_file_path):
    state_dict = torch.load(model_file_path, map_location="cpu", weights_only=False)
    model.load_state_dict(state_dict)
else:
    raise FileNotFoundError("model.pth 文件不存在")
model.load_state_dict(state_dict)

# ['ta_dry_in', 'da_in', 'tw_in', 'Gw', 'Ga'], ['tw_out', 'P']
raw_data = np.array([
    [24.0,0.007449872,18.0,50.001,23564.0,16.80760091,1.408],
    [24.0,0.00934031,18.0,50.001,23564.0,17.53358997,1.408],
    [26.0,0.002080509,18.0,50.001,23564.0,15.05742111,1.408],
    [26.0,0.004174984,18.0,50.001,23564.0,15.86400539,1.408],
    [26.0,0.006283565,18.0,50.001,23564.0,16.673642,1.408],
    [26.0,0.008406397,18.0,50.001,23564.0,17.48550581,1.408],
    [28.0,0.002340857,18.0,50.001,23564.0,15.47563394,1.408],
    [28.0,0.004699402,18.0,50.001,23564.0,16.37879086,1.408],
    [28.0,0.007075835,18.0,50.001,23564.0,17.28574928,1.408],
    [30.0,0.002629291,18.0,50.001,23564.0,15.89937404,1.408],
    [30.0,0.005280907,18.0,50.001,23564.0,16.91061266,1.408],
    [32.0,0.002948346,18.0,50.001,23564.0,16.33061462,1.408],
    [32.0,0.005924778,18.0,50.001,23564.0,17.46024454,1.408],
    [34.0,0.003300741,18.0,50.001,23564.0,16.77141349,1.408],
    [36.0,0.003689391,18.0,50.001,23564.0,17.22109005,1.408],
])
raw_data_tensor = torch.tensor(raw_data, dtype=torch.float32)
input_tensor = raw_data_tensor[:, 0:5]
labels = raw_data_tensor[:, 5:]

model.eval()
with torch.no_grad():
    predictions = model(input_tensor).squeeze()

print(f'labels:\n{labels}')
print(f'predictions:\n{predictions}')
print(f'ERR:\n{(predictions - labels) / labels * 100.0}')
