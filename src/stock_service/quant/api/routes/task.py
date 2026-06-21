"""异步回测任务状态查询 API"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from stock_service.api.dependencies import get_current_user, get_session
from stock_service.crud import quant_crud
from stock_service.schemas.responses import ApiResponse

router = APIRouter(prefix="/api/quant/backtest/task", tags=["quant-task"])


@router.get("/{task_id}", response_model=ApiResponse)
async def get_task_status(
    task_id: int,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(get_current_user),
):
    """查询异步回测任务状态和进度"""
    task = await quant_crud.get_task(session, task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    if task.get("user_id") and task["user_id"] != current_user.id:
        raise HTTPException(403, "Access denied")
    return ApiResponse(code=0, msg="ok", data=task)


@router.get("", response_model=ApiResponse)
async def list_tasks(
    status: str | None = None,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(get_current_user),
):
    """查询异步任务列表（支持 status 过滤）"""
    tasks = await quant_crud.list_tasks(session, user_id=current_user.id, status=status)
    return ApiResponse(code=0, msg="ok", data=tasks)


@router.delete("/{task_id}", response_model=ApiResponse)
async def delete_task(
    task_id: int,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(get_current_user),
):
    """删除异步任务记录"""
    task = await quant_crud.get_task(session, task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    if task.get("user_id") and task["user_id"] != current_user.id:
        raise HTTPException(403, "Access denied")
    if task.get("status") == "running":
        raise HTTPException(409, "Cannot delete a running task. Wait for it to finish or stop the worker.")
    ok = await quant_crud.delete_task(session, task_id)
    if not ok:
        raise HTTPException(404, "Task not found")
    return ApiResponse(code=0, msg="ok")
