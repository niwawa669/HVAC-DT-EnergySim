from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from typing import List, Dict, Any
import pandas as pd
import io
import json
import os

from app.api.deps import get_current_user
from app.services.data_service import data_service

router = APIRouter(prefix="/upload", tags=["upload"])


@router.post("/file")
async def upload_data_file(
    file: UploadFile = File(...),
    current_user: Dict = Depends(get_current_user)
):
    """上传并解析数据文件"""
    
    # ===== 修复：检查文件名是否为 None =====
    if file.filename is None:
        raise HTTPException(
            status_code=400,
            detail="文件名不能为空"
        )
    
    # 检查文件类型
    filename = file.filename.lower()
    if not (filename.endswith('.csv') or filename.endswith('.txt')):
        raise HTTPException(
            status_code=400,
            detail="仅支持 .csv 和 .txt 格式"
        )
    
    # 检查文件大小（限制50MB）
    try:
        # 先读取文件内容
        content = await file.read()
        file_size = len(content)
        
        # 检查文件大小
        max_size = 50 * 1024 * 1024  # 50MB
        if file_size > max_size:
            raise HTTPException(
                status_code=400,
                detail=f"文件大小超过限制 (最大 {max_size // (1024 * 1024)}MB)"
            )
        
        # 解析文件内容
        content_str = content.decode('utf-8')
        
        # 解析数据
        result = data_service.parse_data(content_str)
        
        return {
            "success": True,
            "filename": file.filename,
            **result
        }
        
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400,
            detail="文件编码错误，请使用 UTF-8 编码"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/validate")
async def validate_data(
    data: Dict[str, Any],
    current_user: Dict = Depends(get_current_user)
):
    """校验数据格式"""
    try:
        result = data_service.validate_data(data)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/parse")
async def parse_data(
    data: Dict[str, Any],
    current_user: Dict = Depends(get_current_user)
):
    """解析数据（JSON格式）"""
    try:
        headers = data.get("headers", [])
        rows = data.get("rows", [])
        
        if not headers or not rows:
            raise HTTPException(
                status_code=400,
                detail="数据不能为空"
            )
        
        # 使用 pandas 解析
        df = pd.DataFrame(rows)
        
        # 检测时间列
        time_column = data_service._find_time_column(headers)
        
        return {
            "success": True,
            "headers": headers,
            "rowCount": len(df),
            "columnCount": len(headers),
            "timeColumn": time_column,
            "preview": rows[:10]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))