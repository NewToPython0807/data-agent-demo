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
from app.export import build_csv
from app.history import add_history, clear_history, get_history, init_history_table, list_history
from app.llm import LLMError, generate_sql
from app.metric_resolver import resolve_metric_question
from app.metrics import (
    create_metric,
    delete_metric,
    get_metric,
    list_metric_history,
    list_metrics,
    update_metric,
)
from app.schema import get_user_schema
from app.semantic import (
    get_semantic_layer,
    init_semantic_tables,
    list_columns_with_meta,
    list_tables_with_meta,
    upsert_column_meta,
    upsert_table_meta,
)
from app.sqlguard import SQLGuardError, assert_read_only
from app.upload import UploadError, save_and_import

setup_logging(settings.log_level)
logger = logging.getLogger(__name__)

settings.ensure_dirs()
init_history_table()
init_semantic_tables()

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


class ExportRequest(BaseModel):
    sql: str


class MetaUpdate(BaseModel):
    cn_name: str = ""
    description: str = ""


class MetricCreate(BaseModel):
    name: str
    formula: str
    description: str = ""
    table_name: str = ""
    column_name: str = ""
    unit: str = ""
    dimensions: str = ""


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


@app.get("/api/semantic")
def semantic_layer(username: str = Depends(get_current_user)) -> dict:
    """完整语义层：表/字段中文名 + 指标（受鉴权保护）。"""
    return get_semantic_layer()


@app.get("/api/semantic/tables")
def semantic_tables(username: str = Depends(get_current_user)) -> list[dict]:
    """数据表 + 表级中文名（受鉴权保护，排除内部表）。"""
    return list_tables_with_meta()


@app.put("/api/semantic/tables/{table_name}")
def semantic_table_update(
    table_name: str, body: MetaUpdate, username: str = Depends(get_current_user)
) -> dict:
    """保存表级中文名/说明。"""
    return upsert_table_meta(table_name, body.cn_name, body.description)


@app.get("/api/semantic/tables/{table_name}/columns")
def semantic_columns(
    table_name: str, username: str = Depends(get_current_user)
) -> list[dict]:
    """字段列表 + 字段级中文名。"""
    return list_columns_with_meta(table_name)


@app.put("/api/semantic/tables/{table_name}/columns/{column_name}")
def semantic_column_update(
    table_name: str,
    column_name: str,
    body: MetaUpdate,
    username: str = Depends(get_current_user),
) -> dict:
    """保存字段级中文名/说明。"""
    return upsert_column_meta(table_name, column_name, body.cn_name, body.description)


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
    table: str = Form(""),
    username: str = Depends(get_current_user),
) -> dict:
    """上传 CSV/Excel 导入（受鉴权保护）。table 可选：指定目标表（追加时必填）。"""
    content = await file.read()
    await file.close()
    try:
        return save_and_import(file.filename or "", content, mode, table=table or None)
    except UploadError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/ask")
def ask(body: AskRequest, username: str = Depends(get_current_user)) -> dict:
    """自然语言 → SQL（仅生成，不执行；SQL 由前端展示给用户审核）。"""
    if not body.question.strip():
        raise HTTPException(status_code=400, detail="问题不能为空")

    # 指标直查快路径：裸指标问法（如“销售额”“销售额是多少”）按口径直接展开
    fast_sql = resolve_metric_question(body.question)
    if fast_sql:
        return {"sql": fast_sql, "source": "metric"}

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


@app.post("/api/export")
def export_csv(body: ExportRequest, username: str = Depends(get_current_user)) -> Response:
    """把当前查询结果导出为 CSV（UTF-8 BOM，Excel 可直接打开）。"""
    try:
        assert_read_only(body.sql)
        result = execute_query(body.sql)
    except SQLGuardError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except DatabaseError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    csv_text = build_csv(result["columns"], result["rows"])
    return Response(
        content=csv_text.encode("utf-8"),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="export.csv"'},
    )


@app.get("/api/metrics")
def metrics_list(username: str = Depends(get_current_user)) -> list[dict]:
    """指标列表（受鉴权保护）。"""
    return list_metrics()


@app.post("/api/metrics")
def metrics_create(
    body: MetricCreate, username: str = Depends(get_current_user)
) -> dict:
    """新增指标。"""
    return create_metric(
        body.name,
        body.formula,
        body.description,
        body.table_name,
        body.column_name,
        body.unit,
        body.dimensions,
    )


@app.get("/api/metrics/{metric_id}")
def metrics_detail(metric_id: int, username: str = Depends(get_current_user)) -> dict:
    """指标详情。"""
    item = get_metric(metric_id)
    if item is None:
        raise HTTPException(status_code=404, detail="指标不存在")
    return item


@app.get("/api/metrics/{metric_id}/history")
def metrics_history(
    metric_id: int, username: str = Depends(get_current_user)
) -> list[dict]:
    """指标变更历史（旧版本快照）。"""
    return list_metric_history(metric_id)


@app.put("/api/metrics/{metric_id}")
def metrics_update(
    metric_id: int, body: MetricCreate, username: str = Depends(get_current_user)
) -> dict:
    """更新指标。"""
    item = update_metric(
        metric_id,
        body.name,
        body.formula,
        body.description,
        body.table_name,
        body.column_name,
        body.unit,
        body.dimensions,
    )
    if item is None:
        raise HTTPException(status_code=404, detail="指标不存在")
    return item


@app.delete("/api/metrics/{metric_id}")
def metrics_delete(metric_id: int, username: str = Depends(get_current_user)) -> dict:
    """删除指标。"""
    if not delete_metric(metric_id):
        raise HTTPException(status_code=404, detail="指标不存在")
    return {"ok": True}


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
