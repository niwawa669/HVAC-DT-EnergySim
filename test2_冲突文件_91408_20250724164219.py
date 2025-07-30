import torch
from torch import nn
import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score
from torch.utils.data import Dataset, DataLoader
from torch import optim


input_size = 5
output_size = 1
# model = nn.Sequential(
#     nn.Linear(input_size, 64),
#     nn.ReLU(),
#     nn.Linear(64, 32),
#     nn.ReLU(),
#     nn.Linear(32, 16),
#     nn.ReLU(),
#     nn.Linear(16, output_size),
# )

num = 64
model = nn.Sequential(
    nn.Linear(input_size, num),
    nn.ReLU(),
)
for i in range(2):
    model.add_module(
        f'fc{i}', nn.Linear(int(num / 2**i), int(num / 2**(i+1))),
    )
    model.add_module(
        f'relu{i}', nn.ReLU(),
    )
model = nn.Sequential(
    nn.Linear(input_size, output_size),
)


# class Model(nn.Module):
    
#     def __init__(self, input_size, output_size):
#         super().__init__()
        
#         self.fc1 = nn.Linear(input_size, 64)
#         self.relu1 = nn.ReLU()
#         self.fc2 = nn.Linear(64, 32)
#         self.relu2 = nn.ReLU()
#         self.fc3 = nn.Linear(32, 16)
#         self.relu3 = nn.ReLU()
#         self.fc4 = nn.Linear(16, output_size)
        
#     def forward(self, x):
#         x = self.fc1(x)
#         x = self.relu1(x)
#         x = self.fc2(x)
#         x = self.relu2(x)
#         x = self.fc3(x)
#         x = self.relu3(x)
#         x = self.fc4(x)
#         return x


df = pd.read_table('D:\\BaiduNetdiskWorkspace\\github-project\\冷水机组模拟\\src\\chiller_train_datas.txt')
df = df.loc[:, ['tr_cw', 'G_cw', 'tr_chw', 'G_chw', 'load', 'P']]
X, y = df.loc[:, ['tr_cw', 'G_cw', 'tr_chw', 'G_chw', 'load']], df.loc[:, ['P']]

scaler = MinMaxScaler()
X = scaler.fit_transform(X)

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=20)


class MyDataset(Dataset):
    
    def __init__(self, X, y):
        self.X = torch.tensor(np.array(X), dtype=torch.float32)
        self.y = torch.tensor(np.array(y), dtype=torch.float32)
    
    def __len__(self):
        return len(self.X)
    
    def __getitem__(self, index):
        return self.X[index], self.y[index]


train_loader = DataLoader(MyDataset(X_train, y_train), batch_size=1280, shuffle=True)
X_test = torch.tensor(np.array(X_test), dtype=torch.float32)
y_test = torch.tensor(np.array(y_test), dtype=torch.float32)

# model = Model(5, 1)
loss_func = nn.MSELoss()
optimizer = optim.Adam(model.parameters(), lr=0.001, weight_decay=0.0001)

for epoch in range(2000):
    losses = 0
    num_batch = 0
    for datas, labels in train_loader:
        num_batch += 1
        preds = model(datas)
        loss = loss_func(preds, labels)
        losses += loss.item() / 1280
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
    train_loss = losses / num_batch
    
    with torch.no_grad():
        preds_test = model(X_test)
        loss_test = loss_func(preds_test, y_test)
        test_loss = loss_test.item() / len(X_test)
        r2 = r2_score(y_test, preds_test)
    
    if epoch % 100 == 0:
        print(f'train_loss: {train_loss}, test_loss: {test_loss}, r2_score: {r2}')
