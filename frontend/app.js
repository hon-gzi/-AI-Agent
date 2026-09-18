// 后端地址可配置:默认本机 FastAPI(任务 11 默认 http://127.0.0.1:8000)。
// 部署时若前后端同域(如 nginx 反代),可改为 "" 走相对路径。
const API_BASE = "http://127.0.0.1:8000";

function $(sel) {
  return document.querySelector(sel);
}

// 逗号分隔串 → 字符串数组:trim、去空项(兼容中英文逗号)。
function splitCsv(str) {
  return String(str)
    .split(/[,，]/)
    .map((s) => s.trim())
    .filter((s) => s.length > 0);
}

async function api(path, method = "GET", body) {
  const res = await fetch(API_BASE + path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) {
    let msg = "HTTP " + res.status;
    try {
      const data = await res.json();
      if (data.detail) msg = data.detail;
    } catch (e) {
      /* 非 JSON 响应,保留状态码提示 */
    }
    throw new Error(msg);
  }
  return res.json();
}

function setStatus(el, text, ok = false) {
  el.textContent = text;
  el.classList.toggle("ok", ok);
  el.classList.toggle("err", !ok && text !== "");
}

// ---------- 偏好 ----------
async function loadPrefs() {
  try {
    const data = await api("/api/prefs");
    $("#topics").value = (data.topics || []).join(", ");
    $("#keywords").value = (data.keywords || []).join(", ");
  } catch (e) {
    setStatus($("#prefs-status"), "加载偏好失败: " + e.message);
  }
}

async function savePrefs() {
  const topics = splitCsv($("#topics").value);
  const keywords = splitCsv($("#keywords").value);
  try {
    await api("/api/prefs", "POST", { topics, keywords });
    setStatus($("#prefs-status"), "偏好已保存", true);
  } catch (e) {
    setStatus($("#prefs-status"), "保存失败: " + e.message);
  }
}

// ---------- 生成 ----------
async function generate() {
  const btn = $("#generate");
  const status = $("#generate-status");
  btn.disabled = true;
  setStatus(status, "生成中,请稍候…");
  try {
    const data = await api("/api/trigger", "POST");
    setStatus(status, "生成完成: " + (data.status || "ok"), true);
    await loadHistory();
  } catch (e) {
    setStatus(status, "生成失败: " + e.message);
  } finally {
    btn.disabled = false;
  }
}

// ---------- 历史 ----------
async function loadHistory() {
  const list = $("#history-list");
  list.innerHTML = "";
  const empty = $("#history-empty");
  try {
    const data = await api("/api/briefings");
    const items = data.items || [];
    if (items.length === 0) {
      empty.textContent = "暂无历史简报";
      return;
    }
    empty.textContent = "";
    for (const item of items) {
      const li = document.createElement("li");
      const a = document.createElement("a");
      a.href = "#";
      a.dataset.date = item.date;
      a.textContent = item.date;
      if (item.generated_at) {
        const when = document.createElement("span");
        when.className = "when";
        when.textContent = " · " +
          new Date(item.generated_at * 1000).toLocaleString();
        a.appendChild(when);
      }
      a.addEventListener("click", (ev) => {
        ev.preventDefault();
        selectBriefing(item.date, list);
      });
      li.appendChild(a);
      list.appendChild(li);
    }
  } catch (e) {
    list.innerHTML = "";
    $("#history-empty").textContent = "加载历史失败: " + e.message;
  }
}

async function selectBriefing(date, list) {
  const content = $("#briefing-content");
  // 高亮当前选中项
  list.querySelectorAll("li").forEach((li) => {
    li.classList.toggle("selected", li.querySelector("a") && li.querySelector("a").dataset.date === date);
  });
  try {
    const data = await api("/api/briefings/" + encodeURIComponent(date));
    content.textContent = data.content;
    content.hidden = false;
    content.classList.remove("err");
  } catch (e) {
    content.textContent = "加载简报失败: " + e.message;
    content.hidden = false;
    content.classList.add("err");
  }
}

// ---------- 初始化 ----------
document.addEventListener("DOMContentLoaded", () => {
  $("#save-prefs").addEventListener("click", savePrefs);
  $("#generate").addEventListener("click", generate);

  loadPrefs();
  loadHistory();
});
