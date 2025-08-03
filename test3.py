import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from torch import nn
import torch
from sklearn.metrics import r2_score
from torch.utils.data import Dataset, DataLoader
from torch.optim.lr_scheduler import StepLR
from torch.utils.tensorboard import SummaryWriter


df = pd.read_table('D:\\github-project\\冷水机组模拟\\src\\chiller_train_datas.txt')
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
        self.fc1 = nn.Linear(5, 32)
        self.ln1 = nn.LayerNorm(32)
        self.silu1 = nn.SiLU()
        self.fc2 = nn.Linear(32, 64)
        self.ln2 = nn.LayerNorm(64)
        self.silu2 = nn.SiLU()
        self.fc3 = nn.Linear(64, 128)
        self.ln3 = nn.LayerNorm(128)
        self.silu3 = nn.SiLU()
        self.out = nn.Linear(128, 1)
    
    def forward(self, x):
        x = self.fc1(x)
        x = self.ln1(x)
        x = self.silu1(x)
        x = self.fc2(x)
        x = self.ln2(x)
        x = self.silu2(x)
        x = self.fc3(x)
        x = self.ln3(x)
        x = self.silu3(x)
        x = self.out(x)
        return x

dataset_train = MyDatasets(X_train, y_train)
dataset_test = MyDatasets(X_test, y_test)

dataloader_train = DataLoader(dataset=dataset_train, batch_size=512, shuffle=True)
dataloader_test = DataLoader(dataset=dataset_test, batch_size=512, shuffle=True)

model = Model()
loss_func = nn.MSELoss()
optimizer = torch.optim.AdamW(model.parameters(), lr=0.01, weight_decay=0.01)

activations = {}

def create_hook(layer_name): # 闭包
    def hook(module, input, output):
        activations[layer_name] = output.detach().cpu()
    return hook

for layer_name, layer in model.named_children():
    hook = create_hook(layer_name)
    layer.register_forward_hook(hook)
 
# 选择调度器（示例：StepLR）
scheduler = StepLR(optimizer, step_size=50, gamma=0.1)  # 每5epoch学习率×0.1
writer = SummaryWriter(log_dir='./runs')
 
for epoch in range(1000):
    losses = []
    r2s = []
    for datas, labels in dataloader_train:
        preds = model(datas)
        loss = loss_func(preds, labels)
        losses.append(loss.item())
        r2 = r2_score(labels.detach().numpy(), preds.detach().numpy())
        r2s.append(r2)
        optimizer.zero_grad() 
        loss.backward() 
        optimizer.step() 
        
        for key, val in activations.items():
            writer.add_histogram(f'Activation/{key}', val, epoch)
        activations.clear()
        
        for name, param in model.named_parameters():
            writer.add_histogram(f'Weight/{name}', param.data, epoch)
        
        for name, param in model.named_parameters():
            if param.grad is not None:
                writer.add_histogram(f'Gradiant/{name}', param.grad, epoch)
        
    train_loss = sum(losses) / len(losses)
    writer.add_scalar('Loss/train_loss', train_loss, epoch)
    train_r2 = sum(r2s) / len(r2s)
    writer.add_scalar('R2_score/train_r2', train_r2, epoch)
    
    scheduler.step()   # 更新学习率（按epoch）
    print(f"Epoch {epoch}, train_loss: {train_loss}, train_r2: {train_r2}, LR: {scheduler.get_last_lr()}") 
    
    with torch.no_grad():
        losses = []
        r2s = []
        for datas, labels in dataloader_test:
            outs = model(datas)
            loss = loss_func(outs, labels)
            r2 = r2_score(labels.detach().numpy(), outs.detach().numpy())
            losses.append(loss.item())
            r2s.append(r2)
        test_loss = sum(losses) / len(losses)
        writer.add_scalar('Loss/test_loss', test_loss, epoch)
        test_r2 = sum(r2s) / len(r2s)
        writer.add_scalar('R2_score/test_r2', test_r2, epoch)
        print(f"Epoch {epoch}, test_loss: {test_loss}, test_r2: {test_r2}")
        print()
    