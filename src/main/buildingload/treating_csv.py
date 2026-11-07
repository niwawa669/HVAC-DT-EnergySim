import pandas as pd
import os

file_path = '建筑逐时负荷和气象数据.csv'
file_path = os.path.join(os.path.dirname(__file__), file_path)
df = pd.read_csv(file_path, index_col=0)
df1 = df.loc[:, ['干球温度(℃)', '含湿量(g/Kg)', '冷负荷(kW)']]
df1 = df1[pd.isna(df1['冷负荷(kW)'])]
df1.loc[:, '冷负荷(kW)'] = 0.0
df.update(df1)
df['冷负荷(kW)'] = abs(df['冷负荷(kW)'])
df.columns = ['t_dry', 'd', 'load']
df.index.name = 'datetime'
df['d'] /= 1000.0
df.to_csv('buildingloads_adjusted.csv')
# print(df.loc['2025/1/1 14:00':'2025/1/1 16:00', :])