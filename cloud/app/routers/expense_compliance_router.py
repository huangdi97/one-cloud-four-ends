"""Expense compliance APIs."""

from fastapi import APIRouter, Depends, Query

from cloud.app.schemas.expense_compliance import ExpenseItem
from cloud.app.services.rep_workbench.expense_compliance_service import (
    check_expense,
    get_budget_status,
    suggest_alternative,
)
from shared.auth_scope import require_scope
from shared.base import success

router = APIRouter(prefix="/api/expense", tags=["费用合规"])


@router.post("/check", tags=["费用合规"])
def expense_check(body: ExpenseItem, _: dict = Depends(require_scope("visit"))):
    return success(data=check_expense(body.visit_id, body))


@router.get("/budget/{rep_id}", tags=["费用合规"])
def expense_budget(rep_id: str, period: str = Query("2026-06"), _: dict = Depends(require_scope("visit"))):
    return success(data=get_budget_status(rep_id, period))


@router.post("/suggest", tags=["费用合规"])
def expense_suggest(body: ExpenseItem, _: dict = Depends(require_scope("visit"))):
    return success(data=suggest_alternative(body))
