import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from torch import nn
import torch
from sklearn.metrics import r2_score
from torch.utils.data import Dataset, DataLoader
import joblib
import os
import optuna


df = pd.read_table('D:\\github-project\\冷水机组模拟\\src\\chiller_train_datas1.txt')
df = df.loc[:, ['负荷率', '冷却水进水温度', '冷却水出水温度', '冷冻水回水温度', '冷冻水出水温度', 'COP']]
X, y = df.loc[:, ['负荷率', '冷却水进水温度', '冷却水出水温度', '冷冻水回水温度', '冷冻水出水温度']], df.loc[:, ['COP']]

if os.path.exists('./scaler.joblib'):
    scaler = joblib.load('./scaler.joblib')
else:
    scaler = StandardScaler().fit(X)
    joblib.dump(scaler, './scaler.joblib')
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
    def __init__(self, input_size, output_size, hidden_size, prob_dropout):
        super().__init__()
        self.fc1 = nn.Linear(input_size, hidden_size)
        self.bn1 = nn.BatchNorm1d(hidden_size)
        self.dropout = nn.Dropout(prob_dropout)
        self.relu1 = nn.ReLU()
        self.fc2 = nn.Linear(hidden_size, hidden_size // 2)
        self.relu2 = nn.ReLU()
        self.fc3 = nn.Linear(hidden_size // 2, hidden_size // 4)
        self.relu3 = nn.ReLU()
        self.fc4 = nn.Linear(hidden_size // 4, output_size)
    
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

dataset_train = MyDatasets(X_train, y_train)
dataset_test = MyDatasets(X_test, y_test)

device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')

# if os.path.exists('./model.joblib'):
#     model = joblib.load('./model.joblib')
# else:

def objective(trial:optuna.Trial):
    lr = trial.suggest_float('lr', 1e-5, 1e-1, log=True)
    weight_decay = trial.suggest_float('weight_decay', 1e-5, 1e-3, log=True)
    batch_size = trial.suggest_int('batch_size', 16, 64)
    prob_dropout = trial.suggest_float('prob_dropout', 0.1, 0.5)
    hidden_size = trial.suggest_categorical('hidden_size', [128, 256, 512, 1024])
    
    model = Model(5, 1, hidden_size, prob_dropout)
    model.to(device)
    for layer in model.modules():
        if isinstance(layer, nn.Linear):
            nn.init.kaiming_normal_(layer.weight, nonlinearity='relu')
            nn.init.zeros_(layer.bias)
        
    loss_func = nn.MSELoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer=optimizer,
        mode='min',
        factor=0.5,
        patience=10,
    )
    
    dataloader_train = DataLoader(dataset=dataset_train, batch_size=batch_size, shuffle=True)
    dataloader_test = DataLoader(dataset=dataset_test, batch_size=batch_size)

    test_loss = 0
    for epoch in range(1000):
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
            
        train_loss = sum(train_losses) / len(train_losses)
    
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
            test_r2 = sum(test_r2s) / len(test_r2s)
        scheduler.step(test_loss)
        print(f"Epoch {epoch}, train_loss: {train_loss}, test_loss: {test_loss}, test_r2: {test_r2}")
        
        trial.report(test_loss, epoch)
        if trial.should_prune():
            raise optuna.TrialPruned()
        
    return test_loss
 
 
study = optuna.create_study(direction='maximize', pruner=optuna.pruners.SuccessiveHalvingPruner()) 
study.optimize(objective,  n_trials=100)
# 保存模型
best_trial = study.best_trial
best_model = best_trial.user_attrs['model']
joblib.dump(best_model, './model.joblib')
