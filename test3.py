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


df = pd.read_table('D:\\github-project\\冷水机组模拟\\src\\chiller_train_datas1.txt')
df = df.loc[:, ['负荷率', '冷却水进水温度', '冷却水出水温度', '冷冻水回水温度', '冷冻水出水温度', 'COP']]
X, y = df.loc[:, ['负荷率', '冷却水进水温度', '冷却水出水温度', '冷冻水回水温度', '冷冻水出水温度']], df.loc[:, ['COP']]

scaler = StandardScaler().fit(X)
X = scaler.transform(X)

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

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
        self.net = nn.Sequential(
            nn.Linear(5, 256),
            nn.ReLU(),
            nn.BatchNorm1d(256),
            nn.Dropout(0.4),
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, 1),
        )
    
    def forward(self, x):
        x = self.net(x)
        return x

dataset_train = MyDatasets(X_train, y_train)
dataset_test = MyDatasets(X_test, y_test)

dataloader_train = DataLoader(dataset=dataset_train, batch_size=32, shuffle=True)
dataloader_test = DataLoader(dataset=dataset_test, batch_size=32)

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

model = Model().to(device=device)
for layer in model.modules():
    if isinstance(layer, nn.Linear):
        nn.init.kaiming_normal_(layer.weight, nonlinearity='relu')
        nn.init.constant_(layer.bias, 0)
        
loss_func = nn.MSELoss()
optimizer = torch.optim.AdamW(model.parameters(), lr=0.0005, weight_decay=1e-5)
scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
    optimizer=optimizer,
    mode='min',
    factor=0.5,
    patience=10,
)

activations = {}

def create_hook(layer_name): # 闭包
    def hook(module, input, output):
        activations[layer_name] = output.detach().cpu()
    return hook

for layer_name, layer in model.named_children():
    hook = create_hook(layer_name)
    layer.register_forward_hook(hook)
 
writer = SummaryWriter(log_dir='./runs')

for epoch in range(300):
    train_losses = []
    train_r2s = []
    model.train()
    for datas, labels in dataloader_train:
        datas, labels = datas.to(device), labels.to(device)
        preds = model(datas)
        trainLoss = loss_func(preds, labels)
        optimizer.zero_grad() 
        trainLoss.backward() 
        optimizer.step() 
        
        train_losses.append(trainLoss.item())
        trainR2 = r2_score(labels.cpu().detach().numpy(), preds.cpu().detach().numpy())
        train_r2s.append(trainR2)
        
        for key, val in activations.items():
            writer.add_histogram(f'Activation/{key}', val, epoch)
        activations.clear()
        
        for name, param in model.named_parameters():
            writer.add_histogram(f'Weight/{name}', param.data, epoch)
        
        for name, param in model.named_parameters():
            if param.grad is not None:
                writer.add_histogram(f'Gradiant/{name}', param.grad, epoch)
        
    train_loss = sum(train_losses) / len(train_losses)
    writer.add_scalar('Loss/train_loss', train_loss, epoch)
    train_r2 = sum(train_r2s) / len(train_r2s)
    writer.add_scalar('R2_score/train_r2', train_r2, epoch)
    
    model.eval()
    with torch.no_grad():
        test_losses = []
        test_r2s = []
        for datas, labels in dataloader_test:
            datas, labels = datas.to(device), labels.to(device)
            outs = model(datas)
            testLoss = loss_func(outs, labels)
            testR2 = r2_score(labels.cpu().detach().numpy(), outs.cpu().detach().numpy())
            test_losses.append(testLoss.item())
            test_r2s.append(testR2)
        test_loss = sum(test_losses) / len(test_losses)
        writer.add_scalar('Loss/test_loss', test_loss, epoch)
        test_r2 = sum(test_r2s) / len(test_r2s)
        writer.add_scalar('R2_score/test_r2', test_r2, epoch)
    scheduler.step(test_loss)
    print(f"Epoch {epoch}, train_loss: {train_loss}, test_loss: {test_loss}, test_r2: {test_r2}")
    