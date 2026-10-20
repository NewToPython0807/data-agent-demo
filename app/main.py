"""应用入口（T02/T03）：FastAPI 骨架 + 健康检查 + 静态前端挂载。

当前为阶段 0 的最小可运行骨架，不含业务逻辑。
注意：静态文件挂载在 /static，不要把根路径 / 挂成 catch-all，
否则会遮蔽 /api/* 路由（Starlette 按注册顺序匹配）。
"""
from __future__ import annotations

import logging

from fastapi import Depends, FastAPI, File, Form, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.auth import create_session_token, get_current_user, verify_password
from app.config import BASE_DIR, settings, setup_logging
from app.db import DatabaseError, execute_query
from app.history import add_history, clear_history, get_history, init_history_table, list_history
from app.llm import LLMError, generate_sql
from app.schema import get_user_schema
from app.sqlguard import SQLGuardError, assert_read_only
from app.upload import UploadError, save_and_import

setup_logging(settings.log_level)
logger = logging.getLogger(__name__)

settings.ensure_dirs()
init_history_table()

app = FastAPI(title=settings.app_name, version="0.1.0")


@app.get("/api/health")
def health() -> dict:
    """健康检查：确认服务与配置加载正常。"""
    return {
        "status": "ok",
        "app": settings.app_name,
        "database": str(settings.database_path_abs),
        "llm_configured": bool(settings.deepseek_api_key),
    }


class LoginRequest(BaseModel):
    username: str
    password: str


class ContextTurn(BaseModel):
    question: str
    sql: str


class AskRequest(BaseModel):
    question: str
    context: list[ContextTurn] | None = None


class ExecuteRequest(BaseModel):
    question: str
    sql: str


@app.post("/api/login")
def login(body: LoginRequest, response: Response) -> dict:
    """登录：校验单账号，成功后下发 7 天签名 Cookie 会话。"""
    if not settings.account_username or not settings.account_password_hash:
        raise HTTPException(
            status_code=503,
            detail="服务端未配置账号，请在 .env 设置 ACCOUNT_USERNAME 与 ACCOUNT_PASSWORD_HASH",
        )
    if body.username != settings.account_username or not verify_password(
        body.password, settings.account_password_hash
    ):
        raise HTTPException(status_code=401, detail="账号或密码错误")
    token = create_session_token(body.username)
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.session_max_age_seconds,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return {"ok": True, "username": body.username}


@app.post("/api/logout")
def logout(response: Response) -> dict:
    """登出：清除会话 Cookie。"""
    response.delete_cookie(key=settings.session_cookie_name, path="/")
    return {"ok": True}


@app.get("/api/me")
def me(username: str = Depends(get_current_user)) -> dict:
    """当前登录用户（受鉴权保护）：前端用于判断登录态。"""
    return {"username": username}


@app.get("/api/schema")
def schema(username: str = Depends(get_current_user)) -> list[dict]:
    """数据库表结构（受鉴权保护，排除内部表）。"""
    return get_user_schema()


@app.get("/api/history")
def history_list(
    limit: int = 50, offset: int = 0, username: str = Depends(get_current_user)
) -> list[dict]:
    """查询历史列表（受鉴权保护）。"""
    return list_history(limit=limit, offset=offset)


@app.post("/api/history/clear")
def history_clear(username: str = Depends(get_current_user)) -> dict:
    """清空查询历史（受鉴权保护）。"""
    clear_history()
    return {"ok": True}


@app.get("/api/history/{history_id}")
def history_detail(history_id: int, username: str = Depends(get_current_user)) -> dict:
    """查询历史详情（受鉴权保护）。"""
    item = get_history(history_id)
    if item is None:
        raise HTTPException(status_code=404, detail="记录不存在")
    return item


@app.post("/api/upload")
async def upload(
    file: UploadFile = File(...),
    mode: str = Form("replace"),
    username: str = Depends(get_current_user),
) -> dict:
    """上传 CSV/Excel 导入（受鉴权保护）。"""
    content = await file.read()
    await file.close()
    try:
        return save_and_import(file.filename or "", content, mode)
    except UploadError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/ask")
def ask(body: AskRequest, username: str = Depends(get_current_user)) -> dict:
    """自然语言 → SQL（仅生成，不执行；SQL 由前端展示给用户审核）。"""
    if not body.question.strip():
        raise HTTPException(status_code=400, detail="问题不能为空")
    context = [{"question": t.question, "sql": t.sql} for t in (body.context or [])]
    try:
        sql = generate_sql(body.question, context)
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return {"sql": sql}


@app.post("/api/execute")
def execute(body: ExecuteRequest, username: str = Depends(get_current_user)) -> dict:
    """用户确认后执行 SQL：只读校验 → 执行 → 记录历史。"""
    try:
        assert_read_only(body.sql)
        result = execute_query(body.sql)
        history_id = add_history(body.question, body.sql, result)
    except SQLGuardError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except DatabaseError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "columns": result["columns"],
        "rows": result["rows"],
        "row_count": result["row_count"],
        "history_id": history_id,
    }


# 静态资源（阶段 4 之前为占位页）
static_dir = BASE_DIR / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/", include_in_schema=False)
    def index_page() -> FileResponse:
        """首页（需登录，前端自行校验并跳转）。"""
        return FileResponse(static_dir / "index.html")

    @app.get("/login", include_in_schema=False)
    def login_page() -> FileResponse:
        """登录页。"""
        return FileResponse(static_dir / "login.html")
else:
    logger.warning("static 目录不存在：%s", static_dir)


if __name__ == "__main__":
    import uvicorn

    logger.info(
        "启动服务：host=%s port=%s database=%s",
        settings.host,
        settings.port,
        settings.database_path_abs,
    )
    uvicorn.run(app, host=settings.host, port=settings.port)
