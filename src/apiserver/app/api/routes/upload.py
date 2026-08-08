from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from typing import List, Dict, Any
import pandas as pd
import io
import json

from app.api.deps import get_current_user
from app.services.data_service import data_service

router = APIRouter(prefix="/upload", tags=["upload"])

@router.post("/file")
async def upload_data_file(
    file: UploadFile = File(...),
    current_user: Dict = Depends(get_current_user)
):
    """上传并解析数据文件"""
    # 检查文件类型
    if not file.filename.endswith(('.csv', '.txt')):
        raise HTTPException(
            status_code=400,
            detail="仅支持 .csv 和 .txt 格式"
        )
    
    try:
        # 读取文件内容
        content = await file.read()
        content_str = content.decode('utf-8')
        
        # 解析数据
        result = data_service.parse_data(content_str)
        
        return {
            "success": True,
            "filename": file.filename,
            **result
        }
        
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