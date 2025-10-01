import torch 
import torch.nn  as nn 
from torch.utils.tensorboard  import SummaryWriter 
from torch.optim.lr_scheduler import ExponentialLR
import numpy as np
import matplotlib.pyplot as plt
import time
 
# 生成抛物线数据 y = ax² + bx + c + 噪声
def generate_parabola_data(num_samples=1000, a=2, b=-3, c=1):
    x = torch.rand(num_samples,  1) * 10 - 5  # [-5, 5]
    y = a * x**2 + b * x + c + 0.5 * torch.randn_like(x) 
    return x, y 
 
# 数据集划分
train_x, train_y = generate_parabola_data(2000)
test_x, test_y = generate_parabola_data(500)

    
class FCNet(nn.Module):
    def __init__(self):
        super().__init__()
        self.layer_outputs  = {}  # 存储各层输出 
        
        self.fc1  = nn.Linear(1, 128)
        self.fc2  = nn.Linear(128, 64)
        self.fc3  = nn.Linear(64, 32)
        self.fc4  = nn.Linear(32, 1)
        self.relu  = nn.ReLU()
        
    def forward(self, x):
        # 前向传播
        x = self.relu(self.fc1(x)) 
        x = self.relu(self.fc2(x)) 
        x = self.relu(self.fc3(x)) 
        x = self.fc4(x) 
        return x
    
    def _record_output(self, layer_name, output):
        self.layer_outputs[layer_name]  = output.detach() 


model = FCNet()
def hook_fn(module, input, output):
    model.layer_outputs[id(module)] = output.detach()
model.fc1.register_forward_hook(hook_fn)
model.fc2.register_forward_hook(hook_fn)
model.fc3.register_forward_hook(hook_fn)
model.fc4.register_forward_hook(hook_fn)

writer = SummaryWriter(log_dir='./runs')
criterion = nn.MSELoss()
optimizer = torch.optim.Adam(model.parameters(),  lr=0.1)
scheduler = ExponentialLR(optimizer=optimizer, gamma=0.95)

for epoch in range(1000):
    # 训练步骤 
    pred = model(train_x)
    loss = criterion(pred, train_y)
    optimizer.zero_grad() 
    loss.backward() 
    optimizer.step() 
    
    if epoch % 10 == 0:
        scheduler.step()
    
    # TensorBoard记录（每10个epoch）
    if epoch % 10 == 0:
        # 记录损失和预测结果 [8]()
        writer.add_scalar('Loss/train',  loss.item(),  epoch)
        
        # 记录各层输出分布 [1]()
        for name, output in model.layer_outputs.items(): 
            writer.add_histogram( 
                f"LayerOutput/{name}", 
                output, 
                epoch 
            )
        model.layer_outputs.clear()
            
        # 记录权重分布 
        for name, param in model.named_parameters(): 
            writer.add_histogram(f"Weights/{name}",  param, epoch)
            writer.add_histogram(f"Gradients/{name}",  param.grad,  epoch)
    time.sleep(1)
writer.close() 