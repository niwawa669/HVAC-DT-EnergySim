"""数据集仓储（D4）：文件 + 元数据 + 指纹。

- 内容规范化后按 sha256 命名，天然去重
- 写入先落 .tmp 再 rename，避免半份文件
- 读取前重算指纹，被篡改即拒绝复现
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.orm import Dataset


class DatasetError(RuntimeError):
    """数据集不可用（缺失 / 校验失败）。"""


class DatasetNotFound(DatasetError):
    pass


class DatasetIntegrityError(DatasetError):
    pass


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return None if (math.isnan(value) or math.isinf(value)) else value
    if hasattr(value, "item"):  # numpy 标量
        try:
            return _json_safe(value.item())
        except Exception:  # noqa: BLE001
            return str(value)
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return str(value)


def payload_bytes(
    rows: List[Dict[str, Any]],
    headers: Optional[List[Any]] = None,
    time_column: Optional[str] = None,
) -> bytes:
    """规范化序列化：列顺序按 headers 固定（首列是时间戳，不能被排序打乱）。"""
    head = [str(h) for h in (headers or [])]
    if not head and rows:
        head = [str(k) for k in rows[0].keys()]
    ordered_rows = []
    for row in rows:
        ordered = {h: _json_safe(row.get(h)) for h in head}
        # 不在表头里的键也保留，避免丢列
        for key, value in row.items():
            if str(key) not in ordered:
                ordered[str(key)] = _json_safe(value)
        ordered_rows.append(ordered)
    document = {
        "headers": head,
        "timeColumn": time_column,
        "rows": ordered_rows,
    }
    return json.dumps(
        document, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "wb") as fp:
        fp.write(data)
        fp.flush()
        os.fsync(fp.fileno())
    os.replace(tmp, path)


async def save_from_rows(
    session: AsyncSession,
    *,
    rows: List[Dict[str, Any]],
    headers: Optional[List[Any]] = None,
    time_column: Optional[str] = None,
    filename: Optional[str] = None,
    uploaded_by: Optional[int] = None,
) -> Dataset:
    data = payload_bytes(rows, headers, time_column)
    digest = hashlib.sha256(data).hexdigest()
    path = Path(settings.datasets_dir) / f"{digest}.json"

    existing = await session.get(Dataset, digest)
    if existing is not None:
        if not path.is_file():
            _atomic_write(path, data)
            existing.storage_path = str(path)
            await session.flush()
        return existing

    _atomic_write(path, data)
    dataset = Dataset(
        id=digest,
        filename=filename,
        row_count=len(rows),
        column_count=len(headers or []),
        time_column=time_column,
        headers=[str(h) for h in (headers or [])],
        sha256=digest,
        storage_path=str(path),
        uploaded_by=uploaded_by,
    )
    session.add(dataset)
    await session.flush()
    return dataset


def _read_verified(dataset: Dataset) -> bytes:
    path = Path(dataset.storage_path)
    if not path.is_file():
        raise DatasetNotFound(f"数据集文件不存在: {path}")
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != dataset.sha256:
        raise DatasetIntegrityError(
            f"数据集指纹不一致（登记 {dataset.sha256}），文件可能已被修改: {path}"
        )
    return data


async def load_document(session: AsyncSession, dataset_id: str) -> Tuple[Dataset, Dict[str, Any]]:
    dataset = await session.get(Dataset, dataset_id)
    if dataset is None:
        raise DatasetNotFound(f"数据集不存在: {dataset_id}")
    data = _read_verified(dataset)
    document = json.loads(data.decode("utf-8"))
    return dataset, document


async def load_rows(session: AsyncSession, dataset_id: str) -> Tuple[Dataset, List[Dict[str, Any]]]:
    dataset, document = await load_document(session, dataset_id)
    return dataset, list(document.get("rows") or [])
