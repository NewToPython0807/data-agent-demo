/* 前端逻辑（T19–T23：问数、SQL 审核、结果、表结构、历史）。 */

let currentQuestion = "";
let conversation = []; // [{question, sql}]，最多保留最近 5 轮

async function checkLogin() {
  const res = await fetch("/api/me");
  if (res.status === 401 || !res.ok) {
    window.location.href = "/login";
    return null;
  }
  const data = await res.json();
  document.getElementById("username").textContent = data.username;
  return data.username;
}

function showError(msg) {
  document.getElementById("error").textContent = msg || "";
}

function renderConversation() {
  const area = document.getElementById("conversation-area");
  const box = document.getElementById("conversation");
  if (!conversation.length) {
    area.style.display = "none";
    box.innerHTML = "";
    return;
  }
  area.style.display = "block";
  box.innerHTML = "";
  for (const t of conversation) {
    const div = document.createElement("div");
    div.className = "conv-item";
    const q = document.createElement("div");
    q.textContent = "问：" + t.question;
    const s = document.createElement("pre");
    s.textContent = t.sql;
    div.appendChild(q);
    div.appendChild(s);
    box.appendChild(div);
  }
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

/* ---------- 问数 / SQL 审核 / 执行 ---------- */

function showSql(sql) {
  currentQuestion = document.getElementById("question").value.trim();
  document.getElementById("sql-editor").value = sql;
  document.getElementById("sql-area").style.display = "block";
  document.getElementById("result-area").style.display = "none";
}

function renderResult(data) {
  document.getElementById("result-meta").textContent = `共 ${data.row_count} 行`;
  const box = document.getElementById("result-table");
  box.innerHTML = "";
  if (!data.columns || data.columns.length === 0) {
    box.textContent = "（无列信息）";
  } else {
    box.appendChild(makeTable(data.columns, data.rows || []));
    if ((data.row_count || 0) === 0) {
      const p = document.createElement("p");
      p.className = "empty";
      p.textContent = "没有符合条件的数据";
      box.appendChild(p);
    }
  }
  document.getElementById("result-area").style.display = "block";
}

async function askQuestion() {
  const q = document.getElementById("question").value.trim();
  showError("");
  document.getElementById("sql-area").style.display = "none";
  document.getElementById("result-area").style.display = "none";
  if (!q) {
    showError("请输入问题");
    return;
  }
  const res = await fetch("/api/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question: q, context: conversation.slice(-5) }),
  });
  if (!res.ok) {
    let detail = "生成 SQL 失败";
    try { detail = (await res.json()).detail || detail; } catch (_) {}
    showError(detail);
    return;
  }
  const data = await res.json();
  conversation.push({ question: q, sql: data.sql });
  if (conversation.length > 5) conversation = conversation.slice(-5);
  renderConversation();
  showSql(data.sql);
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
  renderResult(data);
}

/* ---------- 表结构 ---------- */

function renderSchema(schema) {
  const box = document.getElementById("schema-list");
  box.innerHTML = "";
  if (!schema.length) {
    box.textContent = "（还没有数据表，请先上传 CSV/Excel）";
    return;
  }
  for (const t of schema) {
    const h = document.createElement("h4");
    h.textContent = "表 " + t.table;
    box.appendChild(h);
    const ul = document.createElement("ul");
    for (const c of t.columns) {
      const li = document.createElement("li");
      li.textContent = `${c.name} (${c.type || "TEXT"})`;
      ul.appendChild(li);
    }
    box.appendChild(ul);
  }
}

async function loadSchema() {
  const res = await fetch("/api/schema");
  if (!res.ok) {
    let detail = "加载表结构失败";
    try { detail = (await res.json()).detail || detail; } catch (_) {}
    showError(detail);
    return;
  }
  renderSchema(await res.json());
}

/* ---------- 查询历史 ---------- */

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
    div.appendChild(title);

    const detail = document.createElement("div");
    detail.style.display = "none";
    div.appendChild(detail);

    title.addEventListener("click", async () => {
      if (detail.style.display === "none") {
        await showHistoryDetail(item.id, detail);
        detail.style.display = "block";
      } else {
        detail.style.display = "none";
      }
    });
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
    meta.textContent = `共 ${item.result.row_count ?? 0} 行`;
    container.appendChild(meta);
  }
}

async function loadHistory() {
  const res = await fetch("/api/history");
  if (!res.ok) {
    showError("加载历史失败");
    return;
  }
  renderHistory(await res.json());
}

/* ---------- 事件绑定 ---------- */

document.getElementById("ask").addEventListener("click", askQuestion);
document.getElementById("execute").addEventListener("click", executeSql);
document.getElementById("cancel").addEventListener("click", () => {
  document.getElementById("sql-area").style.display = "none";
  showError("");
});

document.getElementById("schema-btn").addEventListener("click", async () => {
  const area = document.getElementById("schema-area");
  if (area.style.display === "none") {
    area.style.display = "block";
    await loadSchema();
  } else {
    area.style.display = "none";
  }
});

document.getElementById("history-btn").addEventListener("click", async () => {
  const area = document.getElementById("history-area");
  if (area.style.display === "none") {
    area.style.display = "block";
    await loadHistory();
  } else {
    area.style.display = "none";
  }
});

document.getElementById("history-clear").addEventListener("click", async () => {
  if (!confirm("确定清空全部查询历史？")) return;
  const res = await fetch("/api/history/clear", { method: "POST" });
  if (res.ok) await loadHistory();
});

document.getElementById("upload-btn").addEventListener("click", async () => {
  const file = document.getElementById("upload-file").files[0];
  const msg = document.getElementById("upload-msg");
  msg.textContent = "";
  if (!file) {
    msg.textContent = "❌ 请先选择文件";
    return;
  }
  const fd = new FormData();
  fd.append("file", file);
  fd.append("mode", document.getElementById("upload-mode").value);
  const res = await fetch("/api/upload", { method: "POST", body: fd });
  const data = await res.json().catch(() => ({}));
  if (res.ok) {
    msg.textContent = `✅ 已导入表 ${data.table}，${data.row_count} 行`;
  } else {
    msg.textContent = "❌ " + (data.detail || "上传失败");
  }
});

document.getElementById("logout").addEventListener("click", async () => {
  await fetch("/api/logout", { method: "POST" });
  window.location.href = "/login";
});

checkLogin();
