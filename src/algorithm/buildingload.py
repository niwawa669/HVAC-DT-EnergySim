import os
import pandas as pd
from datetime import datetime
from typing import Union

class CsvToDataframe:
    """
    从CSV文件中按时间范围筛选数据的类
    
    参数:
    - csv_path: CSV文件路径
    - date_column: 包含时间信息的列名
    - date_format: 时间格式，默认为 '%Y-%m-%d %H:%M:%S'
    """
    
    def __init__(self, csv_path: str, date_column: str, date_format: str = '%Y-%m-%d %H:%M:%S'):
        self.csv_path = csv_path
        self.date_column = date_column
        self.date_format = date_format
        self.df = None
        self._load_data()
    
    def _load_data(self):
        """加载CSV数据"""
        try:
            self.df = pd.read_csv(self.csv_path)
            # 将时间列转换为datetime类型
            self.df[self.date_column] = pd.to_datetime(self.df[self.date_column], format=self.date_format)
        except Exception as e:
            raise ValueError(f"无法加载CSV文件: {e}")
    
    def filter_by_datetime(self, start_datetime: Union[str, datetime], 
                           end_datetime: Union[str, datetime]) -> Union[pd.DataFrame, None]:
        """
        根据起止时间筛选数据
        
        参数:
        - start_datetime: 开始时间 (字符串或datetime对象)
        - end_datetime: 结束时间 (字符串或datetime对象)
        
        返回:
        - 筛选后的DataFrame
        """
        # 转换时间为datetime对象
        if isinstance(start_datetime, str):
            start_dt = datetime.strptime(start_datetime, self.date_format)
        else:
            start_dt = start_datetime
            
        if isinstance(end_datetime, str):
            end_dt = datetime.strptime(end_datetime, self.date_format)
        else:
            end_dt = end_datetime
        
        # 筛选数据
        filtered_df = None
        if self.df is not None:
            filtered_df = self.df[
                (self.df[self.date_column] >= start_dt) & 
                (self.df[self.date_column] <= end_dt)
            ].copy()
        
        return filtered_df
    
    def get_all_data(self) -> Union[pd.DataFrame, None]:
        """返回完整的数据框"""
        return self.df


# 使用示例
if __name__ == "__main__":
    file_path = 'buildingloads_adjusted.csv'
    file_path = os.path.join(os.path.dirname(__file__), 'buildingload', file_path)
    
    # 使用CSVTimeFilter类
    csv_filter = CsvToDataframe(file_path, 'datetime', '%Y/%m/%d %H:%M')
    
    # 筛选时间范围内的数据
    result_df = csv_filter.filter_by_datetime(
        '2025/01/01 14:00', 
        '2025/01/01 16:00'
    )
    
    print("原始数据:")
    print(csv_filter.get_all_data())
    print("\n筛选后的数据:")
    print(result_df)



