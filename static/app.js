/* 前端逻辑（T13 三段式骨架 / T14 数据表页）。 */

let currentQuestion = "";
let conversation = [];
let currentUser = "";
let lastResult = null;
let lastExecutedSql = "";

async function checkLogin() {
  const res = await fetch("/api/me");
  if (res.status === 401 || !res.ok) {
    window.location.href = "/login";
    return null;
  }
  currentUser = (await res.json()).username;
  return currentUser;
}

function showError(msg) {
  document.getElementById("error").textContent = msg || "";
}

function makeTable(columns, rows) {
  const table = document.createElement("table");
  const thead = document.createElement("thead");
  const tr = document.createElement("tr");
  for (const c of columns) {
    const th = document.createElement("th");
    th.textContent = c;
    tr.appendChild(th);
  }
  thead.appendChild(tr);
  table.appendChild(thead);

  const tbody = document.createElement("tbody");
  for (const row of rows) {
    const tr2 = document.createElement("tr");
    for (const cell of row) {
      const td = document.createElement("td");
      td.textContent = cell === null ? "" : String(cell);
      tr2.appendChild(td);
    }
    tbody.appendChild(tr2);
  }
  table.appendChild(tbody);
  return table;
}

function renderResult(data) {
  lastResult = data;
  document.getElementById("result-placeholder").hidden = true;
  document.getElementById("result-meta").textContent = `共 ${data.row_count} 行`;
  const box = document.getElementById("result-table");
  box.innerHTML = "";
  if (!data.columns || data.columns.length === 0) {
    box.textContent = "（无列信息）";
    document.getElementById("export-btn").disabled = true;
    return;
  }
  box.appendChild(makeTable(data.columns, data.rows || []));
  if ((data.row_count || 0) === 0) {
    const p = document.createElement("p");
    p.className = "empty";
    p.textContent = "没有符合条件的数据";
    box.appendChild(p);
  }
  document.getElementById("export-btn").disabled = false;
}

function renderConversation() {
  const box = document.getElementById("conversation-items");
  box.innerHTML = "";
  for (const t of conversation) {
    const turn = document.createElement("div");
    turn.className = "turn";

    const q = document.createElement("div");
    q.className = "bubble user";
    q.textContent = t.question;

    const a = document.createElement("div");
    a.className = "bubble assistant";
    const pre = document.createElement("pre");
    pre.textContent = t.sql || "";
    const badge = document.createElement("span");
    badge.className = "status " + (t.status || "pending");
    badge.textContent =
      t.status === "executed" ? "已执行" : t.status === "cancelled" ? "已取消" : "待执行";
    a.append(pre, badge);

    turn.append(q, a);
    box.appendChild(turn);
  }
  const scroll = document.getElementById("conversation-scroll");
  scroll.scrollTop = scroll.scrollHeight;
}

async function askQuestion() {
  const q = document.getElementById("question").value.trim();
  showError("");
  document.getElementById("sql-area").hidden = true;
  if (!q) {
    showError("请输入问题");
    return;
  }
  const res = await fetch("/api/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question: q,
      context: conversation.slice(-5).map((t) => ({ question: t.question, sql: t.sql })),
    }),
  });
  if (!res.ok) {
    let detail = "生成 SQL 失败";
    try { detail = (await res.json()).detail || detail; } catch (_) {}
    showError(detail);
    return;
  }
  const data = await res.json();
  currentQuestion = q;
  conversation.push({ question: q, sql: data.sql, status: "pending" });
  if (conversation.length > 20) conversation = conversation.slice(-20);
  renderConversation();
  document.getElementById("sql-editor").value = data.sql;
  document.getElementById("sql-area").hidden = false;
}

async function executeSql() {
  const sql = document.getElementById("sql-editor").value.trim();
  showError("");
  if (!sql) {
    showError("SQL 不能为空");
    return;
  }
  const res = await fetch("/api/execute", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question: currentQuestion, sql }),
  });
  const data = await res.json();
  if (!res.ok) {
    showError(data.detail || "执行失败");
    return;
  }
  const last = conversation[conversation.length - 1];
  if (last && last.status === "pending") {
    last.sql = sql;
    last.status = "executed";
    renderConversation();
    document.getElementById("sql-area").hidden = true;
  }
  lastExecutedSql = sql;
  renderResult(data);
}

/* ---------- 数据表页（T14）---------- */

function showTablesMsg(msg) {
  document.getElementById("tables-msg").textContent = msg || "";
}

async function loadTables() {
  const res = await fetch("/api/semantic/tables");
  if (!res.ok) {
    showTablesMsg("加载表清单失败");
    return;
  }
  renderTables(await res.json());
}

function renderTables(list) {
  // 同步“目标表”下拉（追加模式用）
  const sel = document.getElementById("upload-table");
  if (sel) {
    const prev = sel.value;
    sel.innerHTML = '<option value="">（按文件名）</option>';
    for (const t of list) {
      const opt = document.createElement("option");
      opt.value = t.table;
      opt.textContent = t.table + (t.cn_name ? `（${t.cn_name}）` : "");
      sel.appendChild(opt);
    }
    sel.value = prev;
  }

  const box = document.getElementById("table-list");
  box.innerHTML = "";
  document.getElementById("table-detail").hidden = true;
  if (!list.length) {
    box.textContent = "（还没有数据表，请先上传）";
    return;
  }
  for (const t of list) {
    const row = document.createElement("div");
    row.className = "meta-row";

    const name = document.createElement("span");
    name.className = "meta-name";
    name.textContent = t.table;

    const cn = document.createElement("input");
    cn.placeholder = "表中文名";
    cn.value = t.cn_name || "";

    const desc = document.createElement("input");
    desc.placeholder = "说明";
    desc.value = t.description || "";

    const colsBtn = document.createElement("button");
    colsBtn.textContent = "字段";
    colsBtn.addEventListener("click", () => loadColumns(t.table));

    const save = document.createElement("button");
    save.textContent = "保存";
    save.addEventListener("click", async () => {
      const res = await fetch(`/api/semantic/tables/${encodeURIComponent(t.table)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cn_name: cn.value, description: desc.value }),
      });
      showTablesMsg(res.ok ? `表 ${t.table} 已保存` : "保存失败");
    });

    row.append(name, cn, desc, colsBtn, save);
    box.appendChild(row);
  }
}

async function loadColumns(table) {
  const res = await fetch(`/api/semantic/tables/${encodeURIComponent(table)}/columns`);
  if (!res.ok) {
    showTablesMsg("加载字段失败");
    return;
  }
  renderColumns(table, await res.json());
}

function renderColumns(table, cols) {
  document.getElementById("table-detail").hidden = false;
  document.getElementById("table-detail-title").textContent = "字段中文名 · " + table;
  const box = document.getElementById("column-list");
  box.innerHTML = "";
  if (!cols.length) {
    box.textContent = "（无字段）";
    return;
  }
  for (const c of cols) {
    const row = document.createElement("div");
    row.className = "meta-row";

    const name = document.createElement("span");
    name.className = "meta-name";
    name.textContent = `${c.column} (${c.type || "TEXT"})`;

    const cn = document.createElement("input");
    cn.placeholder = "字段中文名";
    cn.value = c.cn_name || "";

    const desc = document.createElement("input");
    desc.placeholder = "说明";
    desc.value = c.description || "";

    const save = document.createElement("button");
    save.textContent = "保存";
    save.addEventListener("click", async () => {
      const res = await fetch(
        `/api/semantic/tables/${encodeURIComponent(table)}/columns/${encodeURIComponent(c.column)}`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ cn_name: cn.value, description: desc.value }),
        }
      );
      showTablesMsg(res.ok ? `字段 ${c.column} 已保存` : "保存失败");
    });

    row.append(name, cn, desc, save);
    box.appendChild(row);
  }
}

document.getElementById("upload-btn").addEventListener("click", async () => {
  const file = document.getElementById("upload-file").files[0];
  const mode = document.getElementById("upload-mode").value;
  const table = document.getElementById("upload-table").value;
  showTablesMsg("");
  if (!file) {
    showTablesMsg("请先选择文件");
    return;
  }
  if (mode === "append" && !table) {
    showTablesMsg("追加模式请先在「目标表」中选择要追加的表");
    return;
  }
  const fd = new FormData();
  fd.append("file", file);
  fd.append("mode", mode);
  if (table) fd.append("table", table);
  const res = await fetch("/api/upload", { method: "POST", body: fd });
  const data = await res.json().catch(() => ({}));
  if (res.ok) {
    showTablesMsg(`已导入表 ${data.table}，${data.row_count} 行`);
    await loadTables();
  } else {
    showTablesMsg("上传失败：" + (data.detail || "（无详情）"));
  }
});

/* ---------- 指标管理页（T15）---------- */

let editingMetricId = null;

function showMetricsMsg(msg) {
  document.getElementById("metrics-msg").textContent = msg || "";
}

function resetMetricForm() {
  editingMetricId = null;
  document.getElementById("metric-form-title").textContent = "新增指标";
  for (const id of [
    "m-name",
    "m-formula",
    "m-table",
    "m-column",
    "m-unit",
    "m-dimensions",
    "m-description",
  ]) {
    document.getElementById(id).value = "";
  }
}

function startEditMetric(m) {
  editingMetricId = m.id;
  document.getElementById("metric-form-title").textContent = `编辑指标 #${m.id}`;
  document.getElementById("m-name").value = m.name || "";
  document.getElementById("m-formula").value = m.formula || "";
  document.getElementById("m-table").value = m.table_name || "";
  document.getElementById("m-column").value = m.column_name || "";
  document.getElementById("m-unit").value = m.unit || "";
  document.getElementById("m-dimensions").value = m.dimensions || "";
  document.getElementById("m-description").value = m.description || "";
  document.getElementById("view-metrics").scrollTop = 0;
}

async function saveMetric() {
  const name = document.getElementById("m-name").value.trim();
  const formula = document.getElementById("m-formula").value.trim();
  if (!name || !formula) {
    showMetricsMsg("指标名称和计算口径为必填");
    return;
  }
  const body = {
    name,
    formula,
    description: document.getElementById("m-description").value.trim(),
    table_name: document.getElementById("m-table").value.trim(),
    column_name: document.getElementById("m-column").value.trim(),
    unit: document.getElementById("m-unit").value.trim(),
    dimensions: document.getElementById("m-dimensions").value.trim(),
  };
  const url = editingMetricId ? `/api/metrics/${editingMetricId}` : "/api/metrics";
  const method = editingMetricId ? "PUT" : "POST";
  const res = await fetch(url, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    let detail = "保存失败";
    try { detail = (await res.json()).detail || detail; } catch (_) {}
    showMetricsMsg(detail);
    return;
  }
  showMetricsMsg(editingMetricId ? "已更新指标" : "已新增指标");
  resetMetricForm();
  await loadMetrics();
}

async function deleteMetric(m) {
  if (!confirm(`确定删除指标「${m.name}」？`)) return;
  const res = await fetch(`/api/metrics/${m.id}`, { method: "DELETE" });
  showMetricsMsg(res.ok ? "已删除指标" : "删除失败");
  if (res.ok) await loadMetrics();
}

async function showMetricHistory(m) {
  const res = await fetch(`/api/metrics/${m.id}/history`);
  if (!res.ok) {
    showMetricsMsg("加载历史失败");
    return;
  }
  const list = await res.json();
  document.getElementById("metric-history").hidden = false;
  document.getElementById("metric-history-title").textContent = `变更历史 · ${m.name}`;
  const box = document.getElementById("metric-history-list");
  box.innerHTML = "";
  if (!list.length) {
    box.textContent = "（暂无历史版本）";
    return;
  }
  for (const h of list) {
    const div = document.createElement("div");
    div.className = "history-entry";
    div.textContent =
      `[${h.changed_at}] ${h.name} = ${h.formula}` +
      (h.description ? ` · 说明：${h.description}` : "") +
      (h.unit ? ` · 单位：${h.unit}` : "") +
      (h.dimensions ? ` · 维度：${h.dimensions}` : "");
    box.appendChild(div);
  }
}

async function loadMetrics() {
  const res = await fetch("/api/metrics");
  if (!res.ok) {
    showMetricsMsg("加载指标失败");
    return;
  }
  renderMetricList(await res.json());
}

function renderMetricList(list) {
  const box = document.getElementById("metric-list");
  box.innerHTML = "";
  if (!list.length) {
    box.textContent = "（暂无指标，请在上方新增）";
    return;
  }
  for (const m of list) {
    const row = document.createElement("div");
    row.className = "metric-row";

    const info = document.createElement("div");
    const title = document.createElement("div");
    title.className = "metric-title";
    title.textContent = `${m.name} = ${m.formula}`;
    const meta = document.createElement("div");
    meta.className = "metric-meta";
    meta.textContent = [
      m.table_name ? `表：${m.table_name}` : "",
      m.column_name ? `字段：${m.column_name}` : "",
      m.unit ? `单位：${m.unit}` : "",
      m.dimensions ? `维度：${m.dimensions}` : "",
      m.description ? `说明：${m.description}` : "",
    ]
      .filter(Boolean)
      .join(" · ");
    info.append(title, meta);

    const actions = document.createElement("div");
    actions.className = "metric-actions";
    const edit = document.createElement("button");
    edit.textContent = "编辑";
    edit.addEventListener("click", () => startEditMetric(m));
    const hist = document.createElement("button");
    hist.textContent = "历史";
    hist.addEventListener("click", () => showMetricHistory(m));
    const del = document.createElement("button");
    del.textContent = "删除";
    del.addEventListener("click", () => deleteMetric(m));
    actions.append(edit, hist, del);

    row.append(info, actions);
    box.appendChild(row);
  }
}

document.getElementById("m-save").addEventListener("click", saveMetric);
document.getElementById("m-reset").addEventListener("click", resetMetricForm);

/* ---------- 历史页（T16）---------- */

function showHistoryMsg(msg) {
  document.getElementById("history-msg").textContent = msg || "";
}

async function loadHistory() {
  const res = await fetch("/api/history");
  if (!res.ok) {
    showHistoryMsg("加载历史失败");
    return;
  }
  renderHistory(await res.json());
}

function renderHistory(list) {
  const box = document.getElementById("history-list");
  box.innerHTML = "";
  if (!list.length) {
    box.textContent = "（暂无历史记录）";
    return;
  }
  for (const item of list) {
    const div = document.createElement("div");
    div.className = "history-item";

    const title = document.createElement("div");
    title.className = "history-title";
    title.textContent = `#${item.id} · ${item.question} · ${item.row_count} 行 · ${item.created_at}`;

    const detail = document.createElement("div");
    detail.className = "history-detail";
    detail.hidden = true;

    title.addEventListener("click", async () => {
      if (detail.hidden) {
        await showHistoryDetail(item.id, detail);
        detail.hidden = false;
      } else {
        detail.hidden = true;
      }
    });

    div.append(title, detail);
    box.appendChild(div);
  }
}

async function showHistoryDetail(id, container) {
  const res = await fetch(`/api/history/${id}`);
  if (!res.ok) {
    container.textContent = "加载详情失败";
    return;
  }
  const item = await res.json();
  container.innerHTML = "";
  const pre = document.createElement("pre");
  pre.textContent = item.sql || "";
  container.appendChild(pre);
  if (item.result && item.result.columns) {
    container.appendChild(makeTable(item.result.columns, item.result.rows || []));
    const meta = document.createElement("div");
    meta.className = "metric-meta";
    meta.textContent = `共 ${item.result.row_count ?? 0} 行`;
    container.appendChild(meta);
  }
}

document.getElementById("history-refresh").addEventListener("click", loadHistory);
document.getElementById("history-clear").addEventListener("click", async () => {
  if (!confirm("确定清空全部查询历史？")) return;
  const res = await fetch("/api/history/clear", { method: "POST" });
  if (res.ok) {
    showHistoryMsg("已清空");
    await loadHistory();
  }
});

/* ---------- 导航切换 ---------- */

function showView(name) {
  const views = {
    ask: document.getElementById("view-ask"),
    tables: document.getElementById("view-tables"),
    metrics: document.getElementById("view-metrics"),
    history: document.getElementById("view-history"),
    settings: document.getElementById("view-settings"),
  };
  for (const [key, el] of Object.entries(views)) {
    el.hidden = key !== name;
  }
  document.getElementById("result-pane").hidden = name !== "ask";
  document.querySelectorAll(".nav-item").forEach((b) => {
    b.classList.toggle("active", b.dataset.view === name);
  });
  if (name === "tables") loadTables();
  if (name === "metrics") loadMetrics();
  if (name === "history") loadHistory();
  if (name === "settings") {
    document.getElementById("settings-username").textContent = currentUser || "（未获取）";
  }
}

document.getElementById("brand").addEventListener("click", () => showView("ask"));
document.querySelectorAll(".nav-item").forEach((b) => {
  b.addEventListener("click", () => showView(b.dataset.view));
});

document.getElementById("ask").addEventListener("click", askQuestion);
document.getElementById("execute").addEventListener("click", executeSql);
document.getElementById("cancel").addEventListener("click", () => {
  const last = conversation[conversation.length - 1];
  if (last && last.status === "pending") last.status = "cancelled";
  renderConversation();
  document.getElementById("sql-area").hidden = true;
  showError("");
});

document.getElementById("logout").addEventListener("click", async () => {
  await fetch("/api/logout", { method: "POST" });
  window.location.href = "/login";
});

document.getElementById("settings-logout").addEventListener("click", async () => {
  await fetch("/api/logout", { method: "POST" });
  window.location.href = "/login";
});

document.getElementById("export-btn").addEventListener("click", async () => {
  if (!lastExecutedSql) return;
  const res = await fetch("/api/export", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sql: lastExecutedSql }),
  });
  if (!res.ok) {
    let detail = "导出失败";
    try { detail = (await res.json()).detail || detail; } catch (_) {}
    showError(detail);
    return;
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "export.csv";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
});

checkLogin();
showView("ask");
