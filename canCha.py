import torch
from torch import nn
from torch.optim.lr_scheduler import StepLR
from torch.utils.tensorboard import SummaryWriter
import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score
from torch.utils.data import Dataset, DataLoader
from torch import optim
import time
from collections import defaultdict

# 模型定义（添加name属性以便识别层）
class Model(nn.Module):
    def __init__(self, input_size, output_size):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_size, 64),
            nn.BatchNorm1d(64),
            nn.Dropout(0.1),
            nn.LeakyReLU(0.01),
            
            nn.Linear(64, 128),
            nn.BatchNorm1d(128),
            nn.Dropout(0.1),
            nn.LeakyReLU(0.01),
            
            nn.Linear(128, 256),
            nn.BatchNorm1d(256),
            nn.Dropout(0.1),
            nn.LeakyReLU(0.01),
            
            nn.Linear(256, 512),
            nn.BatchNorm1d(512),
            nn.Dropout(0.1),
            nn.LeakyReLU(0.01),
            
            nn.Linear(512, output_size)
        )
        
        # 为每层添加可读名称
        for i, layer in enumerate(self.net):
            name = f'layer_{i}_{layer.__class__.__name__}'
        
    def forward(self, x):
        return self.net(x)

# 数据预处理
df = pd.read_table('D:\\BaiduSyncdisk\\github-project\\冷水机组模拟\\src\\chiller_train_datas.txt')
df = df.loc[:, ['tr_cw', 'G_cw', 'tr_chw', 'G_chw', 'load', 'P']]
X, y = df.loc[:, ['tr_cw', 'G_cw', 'tr_chw', 'G_chw', 'load']], df.loc[:, ['P']].values

scaler_X = MinMaxScaler()
X = scaler_X.fit_transform(X)
y = y.astype(np.float32)

# 数据集划分
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=20)

# 数据加载器
class MyDataset(Dataset):
    def __init__(self, X, y):
        self.X = torch.tensor(X, dtype=torch.float32)
        self.y = torch.tensor(y, dtype=torch.float32)
    
    def __len__(self):
        return len(self.X)
    
    def __getitem__(self, index):
        return self.X[index], self.y[index]

train_loader = DataLoader(MyDataset(X_train, y_train), batch_size=512, shuffle=True)
test_loader = DataLoader(MyDataset(X_test, y_test), batch_size=512)

# 初始化TensorBoard Writer
writer = SummaryWriter(log_dir="./runs")

# 特征监控工具
activation_stats = defaultdict(list)

def create_hook(name):
    def hook(module, input, output):
        activation_stats[name].append(output.detach())
    return hook

# 注册前向钩子
model = Model(5, 1)
for name, layer in model.named_children():
    if hasattr(layer, 'name'):  # 如果是自定义命名的层
        layer.register_forward_hook(create_hook(name=name))

# 训练配置
loss_func = nn.HuberLoss(delta=1.0)
optimizer = optim.AdamW(model.parameters(), lr=0.001, weight_decay=0.0001)
scheduler = StepLR(optimizer, step_size=300, gamma=0.5)

try:
    for epoch in range(2000):
        model.train()
        train_loss = 0
        activation_stats.clear()  # 清空上一轮统计
        
        # 训练阶段
        for X_batch, y_batch in train_loader:
            optimizer.zero_grad()
            preds = model(X_batch)
            loss = loss_func(preds, y_batch)
            loss.backward()
            optimizer.step()
            train_loss += loss.item()
        
        train_loss /= len(train_loader)
        
        # 验证阶段
        model.eval()
        test_loss = 0
        all_preds, all_labels = [], []
        with torch.no_grad():
            for X_val, y_val in test_loader:
                preds = model(X_val)
                test_loss += loss_func(preds, y_val).item()
                all_preds.append(preds)
                all_labels.append(y_val)
        
        test_loss /= len(test_loader)
        all_preds = torch.cat(all_preds).numpy()
        all_labels = torch.cat(all_labels).numpy()
        r2 = r2_score(all_labels, all_preds)
        
        # 记录标量数据
        writer.add_scalar("Loss/train", train_loss, epoch)
        writer.add_scalar("Loss/test", test_loss, epoch)
        writer.add_scalar("Metrics/R2", r2, epoch)
        writer.add_scalar("LR", optimizer.param_groups[0]['lr'], epoch)
        
        # 记录特征分布
        for name, acts in activation_stats.items():
            if acts:  # 确保有数据
                writer.add_histogram(f"Activations/{name}", torch.cat(acts), epoch)
        
        # 打印进度
        if epoch % 10 == 0:
            lr = optimizer.param_groups[0]['lr']
            print(f'Epoch {epoch:4d}: train_Huber: {train_loss:.4f}, test_Huber: {test_loss:.4f}, '
                  f'R2: {r2:.4f}, LR: {lr:.2e}')
        
        # 更新学习率和暂停
        scheduler.step()
        time.sleep(1)  # 防止写入冲突

finally:
    # 最终评估
    model.eval()
    with torch.no_grad():
        final_preds = []
        for X_val, _ in test_loader:
            final_preds.append(model(X_val))
        final_preds = torch.cat(final_preds).numpy()
        
        final_r2 = r2_score(y_test, final_preds)
        final_huber = loss_func(torch.tensor(final_preds), torch.tensor(y_test)).item()
        print(f'\nFinal Huber Loss: {final_huber:.4f}')
        print(f'Final R2 Score: {final_r2:.4f}')
        print("\nActual vs Predicted samples:")
        print(np.concatenate([y_test[:5], final_preds[:5]], axis=1))
    
    # 确保关闭writer
    writer.close()
    print("TensorBoard writer closed.")