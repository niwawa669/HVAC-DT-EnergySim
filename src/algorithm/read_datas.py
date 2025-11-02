import pandas as pd
import os


def read_buildingload_datas(file_path):
    path = os.path.join(os.path.dirname(__file__), file_path)
    df = pd.read_table(path, parse_dates=[0], index_col=0, dtype=float)
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index, format='%d/%m/%Y %H:%M')
        if not isinstance(df.index, pd.DatetimeIndex):
            print('!!!发生错误：数据文件中的日期格式错误，正确格式：“2025/1/1 8:00”或“1/5/2025 8:00”.')
    if '冷负荷' not in df.columns:
        print('!!!发生错误：数据文件中的冷负荷数据列的列名应改为“冷负荷”.')
    if '湿球温度' not in df.columns:
        print('!!!发生错误：数据文件中的湿球温度数据列的列名应该改为“湿球温度”.')
    df = df.dropna()
    return df
