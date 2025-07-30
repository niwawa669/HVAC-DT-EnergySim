import torch
from torch import nn
import pandas as pd
import numpy as np
from sklearn.preprocessing import QuantileTransformer
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score
from torch.utils.data import Dataset, DataLoader
from torch import optim

# 全连接模型定义（ELU激活）
class Model(nn.Module):
    def __init__(self, input_size, output_size):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_size, 64),
            nn.BatchNorm1d(64),
            nn.ELU(),
            nn.Linear(64, 128),
            nn.BatchNorm1d(128),
            nn.ELU(),
            nn.Linear(128, 256),
            nn.BatchNorm1d(256),
            nn.ELU(),
            nn.Linear(256, 512),
            nn.BatchNorm1d(512),
            nn.ELU(),
            nn.Linear(512, output_size)
        )
        
    def forward(self, x):
        return self.net(x)

# 数据加载和预处理
df = pd.read_table('D:\\BaiduNetdiskWorkspace\\github-project\\冷水机组模拟\\src\\chiller_train_datas.txt')
df = df.loc[:, ['tr_cw', 'G_cw', 'tr_chw', 'G_chw', 'load', 'P']]
X, y = df.loc[:, ['tr_cw', 'G_cw', 'tr_chw', 'G_chw', 'load']], df.loc[:, ['P']]

# 数据归一化
scaler_X = QuantileTransformer(n_quantiles=10000, random_state=20, output_distribution='normal')
X = scaler_X.fit_transform(X)

# 数据集划分
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=20)

# 数据集类
class MyDataset(Dataset):
    def __init__(self, X, y):
        self.X = torch.tensor(np.array(X), dtype=torch.float32)
        self.y = torch.tensor(np.array(y), dtype=torch.float32)
    
    def __len__(self):
        return len(self.X)
    
    def __getitem__(self, index):
        return self.X[index], self.y[index]

# 数据加载器
train_loader = DataLoader(MyDataset(X_train, y_train), batch_size=512, shuffle=True)
X_test = torch.tensor(np.array(X_test), dtype=torch.float32)
y_test = torch.tensor(np.array(y_test), dtype=torch.float32)

# 模型训练配置
model = Model(5, 1)
loss_func = nn.MSELoss()
optimizer = optim.AdamW(model.parameters(), lr=0.001, weight_decay=0.01)

# 训练循环（移除早停）
for epoch in range(20000):
    model.train()
    losses = 0
    num_batch = 0
    
    for datas, labels in train_loader:
        num_batch += 1
        preds = model(datas)
        loss = loss_func(preds, labels)
        losses += loss.item()
        
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
    
    train_loss = losses / num_batch
    
    # 验证阶段
    with torch.no_grad():
        preds_test = model(X_test)
        test_loss = loss_func(preds_test, y_test).item()
        r2 = r2_score(y_test.numpy(), preds_test.numpy())
    
    # 打印训练进度
    if epoch % 10 == 0:
        print(f'Epoch {epoch}: train_loss: {train_loss:.6f}, test_loss: {test_loss:.6f}, r2_score: {r2:.4f}')

# 最终评估
with torch.no_grad():
    preds_test = model(X_test).numpy()
    
    final_r2 = r2_score(preds_test, y_test)
    print(f'\nFinal R2 Score (actual scale): {final_r2:.4f}')
    
    # 显示实际值对比
    print("\nActual vs Predicted samples:")
    print(np.concatenate([y[:5], preds_test[:5]], axis=1))