"""Cost monitoring routes"""
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from cti_scraper.services import CostMonitorService

router = APIRouter()
templates = Jinja2Templates(directory="src/cti_scraper/templates")


@router.get("/summary")
async def get_cost_summary():
    """Get comprehensive cost summary"""
    try:
        cost_service = CostMonitorService()
        summary = cost_service.get_cost_summary()
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching cost summary: {str(e)}")


@router.get("/mtd")
async def get_month_to_date():
    """Get month-to-date costs"""
    try:
        cost_service = CostMonitorService()
        mtd = cost_service.get_month_to_date_cost()
        return mtd
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching MTD cost: {str(e)}")


@router.get("/daily")
async def get_daily_costs(days: int = 7):
    """Get daily costs for the last N days"""
    try:
        cost_service = CostMonitorService()
        daily = cost_service.get_daily_costs(days=days)
        return {"daily_costs": daily}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching daily costs: {str(e)}")


@router.get("/by-service")
async def get_costs_by_service(days: int = 30):
    """Get costs grouped by AWS service"""
    try:
        cost_service = CostMonitorService()
        by_service = cost_service.get_cost_by_service(days=days)
        return {"service_costs": by_service}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching service costs: {str(e)}")


@router.get("/bedrock")
async def get_bedrock_costs():
    """Get Bedrock-specific costs"""
    try:
        cost_service = CostMonitorService()
        bedrock = cost_service.get_bedrock_costs()
        return bedrock
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching Bedrock costs: {str(e)}")


@router.get("/projected")
async def get_projected_cost():
    """Get projected end-of-month cost"""
    try:
        cost_service = CostMonitorService()
        projected = cost_service.get_projected_cost()
        return projected
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating projected cost: {str(e)}")


@router.get("/alerts")
async def get_budget_alerts():
    """Check budget alert thresholds"""
    try:
        cost_service = CostMonitorService()
        alerts = cost_service.check_budget_alerts()
        return {"alerts": alerts}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error checking alerts: {str(e)}")


@router.get("/dashboard", response_class=HTMLResponse)
async def cost_dashboard(request: Request):
    """Cost monitoring dashboard (HTML)"""
    try:
        cost_service = CostMonitorService()
        summary = cost_service.get_cost_summary()

        return templates.TemplateResponse(
            "cost_dashboard.html",
            {
                "request": request,
                "summary": summary,
                "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error rendering dashboard: {str(e)}")
