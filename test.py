import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.neural_network import MLPRegressor  # 多层感知机
from sklearn.metrics import mean_squared_error, r2_score


data_frame = pd.read_table('D:\\BaiduNetdiskWorkspace\\github-project\\冷水机组模拟\\src\\chiller_train_datas.txt')
data_frame = data_frame.loc[:, ['tr_cw', 'G_cw', 'tr_chw', 'G_chw', 'load', 'P']]
X, y = data_frame.loc[:, ['tr_cw', 'G_cw', 'tr_chw', 'G_chw', 'load']], data_frame.loc[:, ['P']]

std_scaler = StandardScaler()
datas = std_scaler.fit_transform(X)

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42)

model = MLPRegressor(
    hidden_layer_sizes=[40, 5],
    activation='relu',
    solver='adam',
    learning_rate='adaptive',
    learning_rate_init=0.01,
    random_state=42,
    early_stopping=True,
    validation_fraction=0.1,
    max_iter=1000,
)

model.fit(X_train, y_train)

y_pred = model.predict(X_test)
r2 = r2_score(y_pred,y_test)
print(f'r2: {r2}')
