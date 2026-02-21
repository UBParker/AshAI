"""Approval endpoints — approve or deny tool executions."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from helperai.api.deps import get_approval_manager
from helperai.core.approval import ApprovalManager

router = APIRouter()


@router.get("/api/approvals")
async def list_pending(manager: ApprovalManager = Depends(get_approval_manager)):
    return await manager.list_pending()


@router.post("/api/approvals/{approval_id}/approve")
async def approve(
    approval_id: str, manager: ApprovalManager = Depends(get_approval_manager)
):
    try:
        await manager.resolve(approval_id, approved=True)
        return {"status": "approved"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/api/approvals/{approval_id}/deny")
async def deny(
    approval_id: str, manager: ApprovalManager = Depends(get_approval_manager)
):
    try:
        await manager.resolve(approval_id, approved=False)
        return {"status": "denied"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
