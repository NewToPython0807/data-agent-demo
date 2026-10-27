/* 前端逻辑（T13 三段式骨架 / T14 数据表页）。 */

let currentQuestion = "";
let currentPlan = null;
let lastHistoryId = null;
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
  let text = msg || "";
  if (typeof text !== "string") {
    try {
      text = JSON.stringify(text);
    } catch (_) {
      text = String(text);
    }
  }
  document.getElementById("error").textContent = text;
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
  if (data.warnings && data.warnings.length) {
    const warn = document.createElement("div");
    warn.className = "result-warnings";
    warn.textContent = "提示：" + data.warnings.join("；");
    box.appendChild(warn);
  }
  lastHistoryId = data.history_id || null;
  const up = document.getElementById("feedback-up");
  const down = document.getElementById("feedback-down");
  if (up) up.disabled = !lastHistoryId;
  if (down) down.disabled = !lastHistoryId;
  document.getElementById("export-btn").disabled = false;
}

async function sendFeedback(rating) {
  const up = document.getElementById("feedback-up");
  const down = document.getElementById("feedback-down");
  const res = await fetch("/api/feedback", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      history_id: lastHistoryId,
      question: currentQuestion || "手动 SQL",
      sql: lastExecutedSql,
      rating,
    }),
  });
  if (res.ok) {
    if (up) up.disabled = true;
    if (down) down.disabled = true;
    showError(rating > 0 ? "已记录反馈：👍" : "已记录反馈：👎");
  } else {
    showError("反馈失败");
  }
}

function makePlanCard(plan) {
  if (!plan) return null;
  const details = document.createElement("details");
  details.className = "plan-card";
  const summary = document.createElement("summary");
  summary.textContent = "分析过程";
  details.appendChild(summary);

  const lines = [];
  const metrics = plan.metrics || [];
  if (metrics.length) {
    lines.push(
      "指标：" +
        metrics
          .map((m) =>
            typeof m === "string" ? m : `${m.name || ""}${m.formula ? "=" + m.formula : ""}`
          )
          .join("；")
    );
  }
  if ((plan.tables || []).length) lines.push("表：" + plan.tables.join("、"));
  if ((plan.joins || []).length) lines.push("关联：" + plan.joins.join("；"));
  if ((plan.filters || []).length) {
    lines.push(
      "过滤：" +
        plan.filters
          .map((f) =>
            typeof f === "string" ? f : `${f.column || ""} ${f.op || ""} ${f.value ?? ""}`.trim()
          )
          .join("；")
    );
  }
  if ((plan.group_by || []).length) lines.push("分组：" + plan.group_by.join("、"));
  if ((plan.order_by || []).length) lines.push("排序：" + plan.order_by.join("、"));
  if (plan.limit !== null && plan.limit !== undefined) lines.push("限制：" + plan.limit);
  if ((plan.assumptions || []).length) lines.push("假设：" + plan.assumptions.join("；"));
  if ((plan.ambiguities || []).length) lines.push("歧义：" + plan.ambiguities.join("；"));
  if ((plan.missing || []).length) lines.push("缺失：" + plan.missing.join("、"));

  const body = document.createElement("pre");
  body.className = "plan-text";
  body.textContent = lines.length ? lines.join("\n") : "（无）";
  details.appendChild(body);
  return details;
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
    const badge = document.createElement("span");
    badge.className = "status " + (t.status || "pending");

    const planCard = makePlanCard(t.plan);
    if (planCard) a.appendChild(planCard);
    if (t.examples && t.examples.length) {
      const ex = document.createElement("div");
      ex.className = "plan-examples";
      ex.textContent = "参考示例：" + t.examples.map((e) => e.question).join("；");
      a.appendChild(ex);
    }

    if (t.status === "refused") {
      pre.textContent = t.reason || "（无法回答：该问题超出当前数据范围）";
      badge.textContent = "无法回答";
      a.append(pre, badge);
    } else if (t.status === "clarify") {
      pre.textContent = "需要澄清：" + (t.reason || "");
      badge.textContent = "需要澄清";
      const cont = document.createElement("button");
      cont.textContent = "按假设继续";
      cont.addEventListener("click", () => askQuestion(true, t.question));
      a.append(pre, badge, cont);
    } else if (t.status === "corrected") {
      pre.textContent = t.sql || "";
      badge.textContent = "已自动纠正";
      a.append(pre, badge);
    } else {
      pre.textContent = t.sql || "";
      badge.textContent =
        t.status === "executed" ? "已执行" : t.status === "cancelled" ? "已取消" : "待执行";
      a.append(pre, badge);
    }

    turn.append(q, a);
    box.appendChild(turn);
  }
  const scroll = document.getElementById("conversation-scroll");
  scroll.scrollTop = scroll.scrollHeight;
}

async function askQuestion(acceptAssumptions = false, questionOverride = null) {
  const q = (questionOverride || document.getElementById("question").value).trim();
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
      accept_assumptions: acceptAssumptions,
    }),
  });
  if (!res.ok) {
    let detail = "生成 SQL 失败";
    try {
      const data = await res.json();
      if (typeof data.detail === "string") detail = data.detail;
      else if (data.detail) detail = JSON.stringify(data.detail);
    } catch (_) {}
    showError(detail);
    return;
  }
  const data = await res.json();
  currentQuestion = q;
  currentPlan = data.plan || null;
  if (!questionOverride) document.getElementById("question").value = "";
  if (data.refused) {
    conversation.push({
      question: q,
      sql: "",
      status: "refused",
      reason: data.reason || "",
      plan: data.plan,
      examples: data.examples || [],
    });
    if (conversation.length > 20) conversation = conversation.slice(-20);
    renderConversation();
    document.getElementById("sql-area").hidden = true;
    return;
  }
  if (data.clarify) {
    conversation.push({
      question: q,
      sql: "",
      status: "clarify",
      reason: (data.ambiguities || []).join("；"),
      plan: data.plan,
      examples: data.examples || [],
    });
    if (conversation.length > 20) conversation = conversation.slice(-20);
    renderConversation();
    document.getElementById("sql-area").hidden = true;
    return;
  }
  conversation.push({
    question: q,
    sql: data.sql,
    status: "pending",
    plan: data.plan,
    examples: data.examples || [],
  });
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
  const btn = document.getElementById("execute");
  btn.disabled = true;
  btn.textContent = "执行中…";
  try {
    const res = await fetch("/api/execute", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: currentQuestion, sql, plan: currentPlan }),
    });
    const data = await res.json();
    if (!res.ok) {
      showError(
        typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail || "执行失败")
      );
      return;
    }
    if (data.corrected) {
      const lastTurn = conversation[conversation.length - 1];
      if (lastTurn) {
        lastTurn.sql = data.sql;
        lastTurn.status = "corrected";
      }
      document.getElementById("sql-editor").value = data.sql;
      renderConversation();
      showError(`执行失败：${data.error}（已自动纠正为上方 SQL，请审核后再次执行）`);
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
  } finally {
    btn.disabled = false;
    btn.textContent = "确认执行";
  }
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
  loadRelations();
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
    name.textContent = t.table + (t.is_deprecated ? "（已弃用）" : "");

    const cn = document.createElement("input");
    cn.placeholder = "表中文名";
    cn.value = t.cn_name || "";

    const syn = document.createElement("input");
    syn.placeholder = "同义词（逗号分隔）";
    syn.value = t.synonyms || "";

    const ctx = document.createElement("input");
    ctx.placeholder = "业务上下文/注意事项";
    ctx.value = t.context || "";

    const dep = document.createElement("input");
    dep.type = "checkbox";
    dep.checked = !!t.is_deprecated;
    const depLabel = document.createElement("label");
    depLabel.append(dep, document.createTextNode("弃用"));

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
        body: JSON.stringify({
          cn_name: cn.value,
          description: desc.value,
          synonyms: syn.value,
          context: ctx.value,
          is_deprecated: dep.checked ? 1 : 0,
        }),
      });
      showTablesMsg(res.ok ? `表 ${t.table} 已保存` : "保存失败");
      if (res.ok) loadTables();
    });

    row.append(name, cn, syn, ctx, depLabel, desc, colsBtn, save);
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
    name.textContent = `${c.column} (${c.type || "TEXT"})` + (c.is_deprecated ? "（已弃用）" : "");

    const cn = document.createElement("input");
    cn.placeholder = "字段中文名";
    cn.value = c.cn_name || "";

    const syn = document.createElement("input");
    syn.placeholder = "同义词";
    syn.value = c.synonyms || "";

    const ctx = document.createElement("input");
    ctx.placeholder = "业务上下文";
    ctx.value = c.context || "";

    const dep = document.createElement("input");
    dep.type = "checkbox";
    dep.checked = !!c.is_deprecated;
    const depLabel = document.createElement("label");
    depLabel.append(dep, document.createTextNode("弃用"));

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
          body: JSON.stringify({
            cn_name: cn.value,
            description: desc.value,
            synonyms: syn.value,
            context: ctx.value,
            is_deprecated: dep.checked ? 1 : 0,
          }),
        }
      );
      showTablesMsg(res.ok ? `字段 ${c.column} 已保存` : "保存失败");
      if (res.ok) loadColumns(table);
    });

    row.append(name, cn, syn, ctx, depLabel, desc, save);
    box.appendChild(row);
  }
}

async function loadRelations() {
  const res = await fetch("/api/semantic/relations");
  if (!res.ok) return;
  renderRelations(await res.json());
}

function renderRelations(list) {
  const box = document.getElementById("relation-list");
  if (!box) return;
  box.innerHTML = "";
  if (!list.length) {
    box.textContent = "（还没有表关系，可添加 JOIN 键）";
    return;
  }
  for (const r of list) {
    const row = document.createElement("div");
    row.className = "meta-row";

    const text = document.createElement("span");
    text.className = "meta-name";
    text.textContent =
      `${r.left_table}.${r.left_column} = ${r.right_table}.${r.right_column}` +
      (r.description ? `（${r.description}）` : "");

    const del = document.createElement("button");
    del.textContent = "删除";
    del.addEventListener("click", async () => {
      const res = await fetch(`/api/semantic/relations/${r.id}`, { method: "DELETE" });
      showTablesMsg(res.ok ? "表关系已删除" : "删除失败");
      if (res.ok) loadRelations();
    });

    row.append(text, del);
    box.appendChild(row);
  }
}

document.getElementById("rel-add").addEventListener("click", async () => {
  const body = {
    left_table: document.getElementById("rel-left-table").value.trim(),
    left_column: document.getElementById("rel-left-column").value.trim(),
    right_table: document.getElementById("rel-right-table").value.trim(),
    right_column: document.getElementById("rel-right-column").value.trim(),
    description: document.getElementById("rel-description").value.trim(),
  };
  showTablesMsg("");
  if (!body.left_table || !body.left_column || !body.right_table || !body.right_column) {
    showTablesMsg("请填写完整的左表/左字段/右表/右字段");
    return;
  }
  const res = await fetch("/api/semantic/relations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (res.ok) {
    showTablesMsg("表关系已添加");
    document.getElementById("rel-description").value = "";
    await loadRelations();
  } else {
    showTablesMsg("添加失败");
  }
});

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

async function loadStats() {
  const box = document.getElementById("stats-card");
  if (!box) return;
  const res = await fetch("/api/feedback/stats");
  if (!res.ok) return;
  const s = await res.json();
  box.innerHTML = "";
  const items = [
    ["查询数", s.queries ?? 0],
    ["👍 赞", s.up ?? 0],
    ["👎 踩", s.down ?? 0],
    ["赞率", (s.up_rate ?? 0) + "%"],
    [
      "golden 通过",
      `${(s.golden && s.golden.passed) ?? 0}/${(s.golden && s.golden.total) ?? 0}`,
    ],
  ];
  for (const [label, value] of items) {
    const item = document.createElement("div");
    item.className = "stats-item";
    const l = document.createElement("span");
    l.className = "stats-label";
    l.textContent = label;
    const v = document.createElement("strong");
    v.textContent = value;
    item.append(l, v);
    box.appendChild(item);
  }
}

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
  if (name === "history") {
    loadHistory();
    loadStats();
  }
  if (name === "settings") {
    document.getElementById("settings-username").textContent = currentUser || "（未获取）";
    loadGolden();
  }
}

async function loadGolden() {
  const res = await fetch("/api/golden");
  if (!res.ok) return;
  renderGolden(await res.json());
}

function renderGolden(list) {
  const box = document.getElementById("golden-list");
  if (!box) return;
  box.innerHTML = "";
  if (!list.length) {
    box.textContent = "（还没有示例）";
    return;
  }
  for (const g of list) {
    const row = document.createElement("div");
    row.className = "meta-row";
    const q = document.createElement("span");
    q.className = "meta-name";
    q.textContent = g.question;
    const sql = document.createElement("span");
    sql.className = "meta-name";
    sql.textContent = g.sql;
    const del = document.createElement("button");
    del.textContent = "删除";
    del.addEventListener("click", async () => {
      const res = await fetch(`/api/golden/${g.id}`, { method: "DELETE" });
      document.getElementById("golden-msg").textContent = res.ok ? "示例已删除" : "删除失败";
      if (res.ok) loadGolden();
    });
    row.append(q, sql, del);
    box.appendChild(row);
  }
}

document.getElementById("golden-add").addEventListener("click", async () => {
  const body = {
    question: document.getElementById("golden-question").value.trim(),
    sql: document.getElementById("golden-sql").value.trim(),
    tags: document.getElementById("golden-tags").value.trim(),
  };
  const msg = document.getElementById("golden-msg");
  msg.textContent = "";
  if (!body.question || !body.sql) {
    msg.textContent = "请填写问题与 SQL";
    return;
  }
  const res = await fetch("/api/golden", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (res.ok) {
    msg.textContent = "示例已添加";
    document.getElementById("golden-question").value = "";
    document.getElementById("golden-sql").value = "";
    document.getElementById("golden-tags").value = "";
    await loadGolden();
  } else {
    msg.textContent = "添加失败";
  }
});

document.getElementById("brand").addEventListener("click", () => showView("ask"));
document.querySelectorAll(".nav-item").forEach((b) => {
  b.addEventListener("click", () => showView(b.dataset.view));
});

document.getElementById("ask").addEventListener("click", () => askQuestion());
document.getElementById("question").addEventListener("keydown", (e) => {
  // Enter 发送；Ctrl/Cmd/Shift/Alt + Enter 换行
  if (e.key === "Enter" && !e.ctrlKey && !e.metaKey && !e.shiftKey && !e.altKey) {
    e.preventDefault();
    askQuestion();
  }
});
document.getElementById("execute").addEventListener("click", executeSql);
document.getElementById("feedback-up").addEventListener("click", () => sendFeedback(1));
document.getElementById("feedback-down").addEventListener("click", () => sendFeedback(-1));
document.getElementById("raw-execute").addEventListener("click", async () => {
  const sql = document.getElementById("raw-sql").value.trim();
  const msg = document.getElementById("raw-msg");
  msg.textContent = "";
  if (!sql) {
    msg.textContent = "请输入 SQL";
    return;
  }
  const btn = document.getElementById("raw-execute");
  btn.disabled = true;
  btn.textContent = "执行中…";
  try {
    const res = await fetch("/api/execute", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: "手动 SQL", sql }),
    });
    const data = await res.json();
    if (!res.ok) {
      msg.textContent =
        typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail || "执行失败");
      return;
    }
    if (data.corrected) {
      document.getElementById("raw-sql").value = data.sql;
      msg.textContent = `执行失败：${data.error}（已自动纠正，请审核后再次执行）`;
      return;
    }
    renderResult(data);
    lastExecutedSql = sql;
    msg.textContent = "已执行";
  } finally {
    btn.disabled = false;
    btn.textContent = "执行 SQL";
  }
});
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
    try {
      const data = await res.json();
      if (typeof data.detail === "string") detail = data.detail;
      else if (data.detail) detail = JSON.stringify(data.detail);
    } catch (_) {}
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
