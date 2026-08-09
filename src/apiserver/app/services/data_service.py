import pandas as pd
import numpy as np
from typing import Dict, Any, List, Tuple
import io
import re

class DataService:
    """数据处理服务"""
    
    def parse_data(self, content: str) -> Dict[str, Any]:
        """解析 CSV/TXT 数据"""
        
        # ===== 修复：检查内容是否为空 =====
        if not content or not content.strip():
            return {
                "headers": [],
                "rows": [],
                "rowCount": 0,
                "columnCount": 0,
                "timeColumn": None,
                "preview": [],
                "warnings": ["文件内容为空"]
            }
        
        try:
            # 检测分隔符
            delimiter = self._detect_delimiter(content)
            
            # 使用 pandas 读取
            df = pd.read_csv(
                io.StringIO(content),
                delimiter=delimiter,
                encoding='utf-8',
                engine='python'  # 使用 Python 引擎，兼容性更好
            )
            
            # 获取列名
            headers = df.columns.tolist()
            
            # 转换为字典列表
            rows = df.to_dict('records')
            
            # 检测时间列
            time_column = self._find_time_column(headers)
            
            return {
                "headers": headers,
                "rows": rows,
                "rowCount": len(df),
                "columnCount": len(headers),
                "timeColumn": time_column,
                "preview": rows[:10],
                "warnings": []
            }
            
        except pd.errors.EmptyDataError:
            return {
                "headers": [],
                "rows": [],
                "rowCount": 0,
                "columnCount": 0,
                "timeColumn": None,
                "preview": [],
                "warnings": ["文件为空"]
            }
        except Exception as e:
            return {
                "headers": [],
                "rows": [],
                "rowCount": 0,
                "columnCount": 0,
                "timeColumn": None,
                "preview": [],
                "warnings": [f"解析错误: {str(e)}"]
            }
    
    def validate_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """校验数据"""
        headers = data.get("headers", [])
        rows = data.get("rows", [])
        
        if not rows:
            return {
                "isValid": False,
                "errors": [{"message": "数据为空"}],
                "warnings": [],
                "summary": {"totalRows": 0, "validRows": 0, "invalidRows": 0}
            }
        
        df = pd.DataFrame(rows)
        errors = []
        warnings = []
        valid_rows = 0
        invalid_rows = 0
        
        # 检查时间列
        time_column = self._find_time_column(headers)
        if not time_column:
            errors.append({
                "row": -1,
                "column": "时间戳",
                "message": "未找到时间列，请确保列名包含'时间'、'日期'、'time'或'date'"
            })
        
        # 检查每行数据
        for idx, row in enumerate(rows):
            row_valid = True
            
            # 检查时间格式
            if time_column:
                time_val = row.get(time_column)
                if time_val is None or str(time_val).strip() == '':
                    errors.append({
                        "row": idx,
                        "column": time_column,
                        "value": time_val,
                        "message": "时间戳为空"
                    })
                    row_valid = False
                else:
                    # 验证时间格式
                    formatted = self._format_timestamp(time_val)
                    if formatted != str(time_val):
                        errors.append({
                            "row": idx,
                            "column": time_column,
                            "value": time_val,
                            "message": "时间格式不正确，应为 YYYY-MM-DD HH:00",
                            "suggestion": formatted
                        })
                        row_valid = False
            
            # 检查数值列
            for header in headers:
                if header == time_column:
                    continue
                value = row.get(header)
                if value is None or str(value).strip() == '':
                    errors.append({
                        "row": idx,
                        "column": header,
                        "value": value,
                        "message": "数据缺失",
                        "suggestion": 0
                    })
                    row_valid = False
                else:
                    try:
                        float(value)
                    except (ValueError, TypeError):
                        errors.append({
                            "row": idx,
                            "column": header,
                            "value": value,
                            "message": f"'{value}' 不是有效数字",
                            "suggestion": 0
                        })
                        row_valid = False
            
            if row_valid:
                valid_rows += 1
            else:
                invalid_rows += 1
        
        return {
            "isValid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "summary": {
                "totalRows": len(rows),
                "validRows": valid_rows,
                "invalidRows": invalid_rows
            }
        }
    
    def _detect_delimiter(self, content: str) -> str:
        """检测分隔符"""
        first_line = content.split('\n')[0] if content else ""
        if '\t' in first_line:
            return '\t'
        elif ';' in first_line:
            return ';'
        else:
            return ','
    
    def _find_time_column(self, headers: List[str]) -> str:
        """查找时间列"""
        if not headers:
            return ''
        time_keywords = ['时间', '日期', 'time', 'date', 'timestamp', '时刻']
        for header in headers:
            header_lower = header.lower()
            if any(keyword in header_lower for keyword in time_keywords):
                return header
        return ''
    
    def _format_timestamp(self, value) -> str:
        """格式化时间戳"""
        value_str = str(value).strip()
        
        if not value_str:
            return value_str
        
        # 尝试多种格式
        patterns = [
            (r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})\s+(\d{1,2}):(\d{2})', 
             lambda m: f"{m[1]}-{int(m[2]):02d}-{int(m[3]):02d} {int(m[4]):02d}:00"),
            (r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})\s+(\d{1,2})',
             lambda m: f"{m[1]}-{int(m[2]):02d}-{int(m[3]):02d} {int(m[4]):02d}:00"),
            (r'(\d{1,2})[-/](\d{1,2})[-/](\d{4})\s+(\d{1,2}):(\d{2})',
             lambda m: f"{m[3]}-{int(m[1]):02d}-{int(m[2]):02d} {int(m[4]):02d}:00"),
            (r'(\d{1,2})[-/](\d{1,2})[-/](\d{4})\s+(\d{1,2})',
             lambda m: f"{m[3]}-{int(m[1]):02d}-{int(m[2]):02d} {int(m[4]):02d}:00"),
            (r'(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})',
             lambda m: f"{m[1]}-{m[2]}-{m[3]} {m[4]}:00"),
        ]
        
        for pattern, formatter in patterns:
            match = re.match(pattern, value_str)
            if match:
                return formatter(match)
        
        return value_str

data_service = DataService()