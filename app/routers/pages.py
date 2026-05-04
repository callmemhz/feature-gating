"""页面路由"""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from app.deps import get_optional_user, templates, get_flashed_messages

router = APIRouter(tags=["pages"])


@router.get("/", response_class=HTMLResponse)
async def index(request: Request, current_user: dict = Depends(get_optional_user)):
    """主页面"""
    return templates.TemplateResponse(request, "index.html", {
        "user": current_user,
        "messages": get_flashed_messages(request)
    })


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """登录页面"""
    return templates.TemplateResponse(request, "login.html", {
        "messages": get_flashed_messages(request)
    })


@router.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request, current_user: dict = Depends(get_optional_user)):
    """管理页面"""
    return templates.TemplateResponse(request, "admin.html", {
        "user": current_user,
        "messages": get_flashed_messages(request)
    })

