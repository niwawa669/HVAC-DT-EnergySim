import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from torch import nn
import torch
from sklearn.metrics import r2_score
from torch.utils.data import Dataset, DataLoader


df = pd.read_table('D:\\BaiduNetdiskWorkspace\\github-project\\冷水机组模拟\\src\\chiller_train_datas.txt')
df = df.loc[:, ['tr_cw', 'G_cw', 'tr_chw', 'G_chw', 'load', 'P']]
X, y = df.loc[:, ['tr_cw', 'G_cw', 'tr_chw', 'G_chw', 'load']], df.loc[:, ['P']]

scaler = StandardScaler().fit(X)
X = scaler.transform(X)

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42)

class MyDatasets(Dataset):
    
    def __init__(self, data, label):
        self.data = torch.tensor(np.array(data), dtype=torch.float32)
        self.label = torch.tensor(np.array(label), dtype=torch.float32)
    
    def __len__(self):
        return len(self.data)
    
    def __getitem__(self, idx):
        return self.data[idx], self.label[idx]

class Model(nn.Module):
    def __init__(self):
        super().__init__()
        self.fc1 = nn.Linear(5, 40)
        self.relu1 = nn.ReLU()
        self.fc2 = nn.Linear(40, 5)
        self.relu2 = nn.ReLU()
        self.out = nn.Linear(5, 1)
    
    def forward(self, x):
        x = self.fc1(x)
        x = self.relu1(x)
        x = self.fc2(x)
        x = self.relu2(x)
        x = self.out(x)
        return x

dataset_train = MyDatasets(X_train, y_train)
dataset_test = MyDatasets(X_test, y_test)

dataloader_train = DataLoader(dataset=dataset_train, batch_size=100, shuffle=True)
dataloader_test = DataLoader(dataset=dataset_test, batch_size=100, shuffle=True)

model = Model()
loss_func = nn.MSELoss()
optimizer = torch.optim.Adam(model.parameters(), lr=0.1)

for epoch in range(1000):
    for batch_idx, (data, label) in enumerate(dataloader_train):
        model.train(True)
        optimizer.zero_grad()
        preds = model(data)
        loss = loss_func(preds, label)
        loss.backward()
        optimizer.step()
        
        if batch_idx % 10 == 0:
            print(f'epoch: {epoch}, batch_idx: {batch_idx}, loss: {loss}')

model.train(False)
with torch.no_grad():
    sum_r2 = 0
    num = 0
    for batch_idx, (data, label) in enumerate(dataloader_test):
        out = model(data)
        r2 = r2_score(label, out)
        sum_r2 += r2
        num = batch_idx + 1
    print(f'r2: {sum_r2 / num}')
