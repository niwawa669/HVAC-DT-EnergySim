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
from datetime import datetime
import optuna

# 初始化TensorBoard
log_dir = f"logs/huber_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
writer = SummaryWriter(log_dir)

def objective(trial):
    params = {
        'lr': trial.suggest_float('lr', 1e-5, 1e-2, log=True),
        'weight_decay': trial.suggest_float('weight_decay', 1e-6, 1e-3, log=True),
        'dropout_rate': trial.suggest_float('dropout_rate', 0.0, 0.5),
        'hidden_dim1': trial.suggest_categorical('hidden_dim1', [32, 64, 128, 256]),
        'hidden_dim2': trial.suggest_categorical('hidden_dim2', [64, 128, 256, 512]),
        'delta': trial.suggest_float('delta', 0.5, 2.0)
    }

# 模型定义（添加记录钩子）
class Model(nn.Module):
    def __init__(self, input_size, output_size):
        super().__init__()
        self.layers = nn.Sequential(
            nn.Linear(input_size, param['hidden_dim1']),
            nn.LayerNorm(param['hidden_dim2']),
            nn.LeakyReLU(0.01),
            
            nn.Linear(param['hidden_dim1'], param['hidden_dim2']),
            nn.LayerNorm(param['hidden_dim2']),
            nn.LeakyReLU(0.01),
            
            nn.Linear(param['hidden_dim1'], param['hidden_dim2']),
            nn.LayerNorm(param['hidden_dim2']),
            nn.LeakyReLU(0.01),
            
            nn.Linear(param['hidden_dim1'], param['hidden_dim2']),
            nn.LayerNorm(param['hidden_dim2']),
            nn.LeakyReLU(0.01),
            
            nn.Linear(param['hidden_dim2'], output_size)
        )
        
        # 注册前向/反向钩子
        self._register_hooks()
        
    def forward(self, x):
        return self.layers(x)
    
    def _register_hooks(self):
        for i, layer in enumerate(self.layers):
            if isinstance(layer, nn.Linear):
                # 前向钩子记录输入/输出
                layer.register_forward_hook(
                    lambda module, input, output, idx=i: 
                    writer.add_histogram(f'Layer_{idx}/input', input[0], global_step)
                )
                layer.register_forward_hook(
                    lambda module, input, output, idx=i: 
                    writer.add_histogram(f'Layer_{idx}/output', output, global_step)
                )
                # 反向钩子记录梯度
                layer.register_full_backward_hook(
                    lambda module, grad_input, grad_output, idx=i: 
                    writer.add_histogram(f'Layer_{idx}/gradient', grad_output[0], global_step)
                )
                # 参数记录
                layer.register_forward_hook(
                    lambda module, input, output, idx=i: 
                    writer.add_histogram(f'Layer_{idx}/weight', module.weight, global_step)
                )

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

# 模型配置
model = Model(5, 1)
loss_func = nn.HuberLoss(delta=1.0)
optimizer = optim.AdamW(model.parameters(), lr=param['lr'], weight_decay=0.0001)
scheduler = StepLR(optimizer, step_size=300, gamma=0.5)

# 训练循环
global_step = 0
for epoch in range(2000):
    model.train()
    train_loss = 0
    
    for X_batch, y_batch in train_loader:
        optimizer.zero_grad()
        preds = model(X_batch)
        loss = loss_func(preds, y_batch)
        loss.backward()
        
        # 记录全局梯度
        for name, param in model.named_parameters():
            if param.grad is not None:
                writer.add_histogram(f'Global_Grad/{name}', param.grad, global_step)
        
        optimizer.step()
        train_loss += loss.item()
        global_step += 1  # 更新全局步数
    
    train_loss /= len(train_loader)
    writer.add_scalar('Loss/train', train_loss, epoch)
    
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
    
    writer.add_scalar('Loss/test', test_loss, epoch)
    writer.add_scalar('Metric/R2', r2, epoch)
    
    # 更新学习率
    scheduler.step()
    writer.add_scalar('LR', optimizer.param_groups[0]['lr'], epoch)
    
    if epoch % 10 == 0:
        print(f'Epoch {epoch:4d}: train_Huber: {train_loss:.4f}, test_Huber: {test_loss:.4f}, R2: {r2:.4f}')

# 最终评估
model.eval()
with torch.no_grad():
    final_preds = torch.cat([model(X_val) for X_val, _ in test_loader]).numpy()
    final_r2 = r2_score(y_test, final_preds)
    final_huber = loss_func(torch.tensor(final_preds), torch.tensor(y_test)).item()
    
    print(f'\nFinal Huber Loss: {final_huber:.4f}')
    print(f'Final R2 Score: {final_r2:.4f}')
    print("\nActual vs Predicted samples:")
    print(np.concatenate([y_test[:5], final_preds[:5]], axis=1))

# 关闭TensorBoard
writer.close()