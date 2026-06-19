from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse

from .agent import user_chat
from .config import get_settings
from .game_agent import KING_GAME, chat_with_companion, update_memory
from .local_memory import LocalPlayerMemory
from .memory import memory_manage
from .schemas import (
    ChatRequest,
    ChatResponse,
    CompanionChatRequest,
    CompanionChatResponse,
    MemoryRequest,
    MemoryResponse,
    PlanRequest,
    PlayerMemoryWriteRequest,
    RecommendRequest,
    ToolInvokeRequest,
    ToolInvokeResponse,
    TraceResponse,
)
from .tools import build_recommend, guide_search, task_plan_tool, tool_invoke
from .tracer import TraceStore


app = FastAPI(title="Honor of Kings AI Assistant", version="0.3.0")
PACKAGE_DIR = Path(__file__).resolve().parent
GUIDES_FILE = PACKAGE_DIR / "knowledge" / "game_guides.json"


def _load_json(path: Path) -> list[dict[str, Any]]:
    """Load JSON list data for lightweight API endpoints."""
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


HTML_TEMPLATE = """
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>电竞AI教练系统 - 王者荣耀</title>
  <style>
    :root {
      font-family: "Microsoft YaHei", "Segoe UI", Arial, sans-serif;
      color: #edf4ff;
      background: #080d18;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      background:
        radial-gradient(circle at 18% 12%, rgba(37, 99, 235, 0.25), transparent 26%),
        radial-gradient(circle at 82% 8%, rgba(14, 165, 233, 0.16), transparent 24%),
        linear-gradient(135deg, #080d18 0%, #10182d 50%, #090d18 100%);
    }
    header {
      min-height: 70px;
      padding: 14px 22px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 18px;
      background: rgba(5, 10, 22, 0.94);
      border-bottom: 1px solid rgba(96, 165, 250, 0.24);
    }
    h1 { margin: 0; font-size: 23px; letter-spacing: 0; }
    .subtitle { margin-top: 5px; color: #9db4ee; font-size: 13px; }
    .status { display: flex; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }
    .pill {
      display: inline-flex;
      align-items: center;
      border: 1px solid rgba(125, 160, 255, 0.35);
      background: rgba(24, 35, 68, 0.78);
      color: #dce8ff;
      border-radius: 999px;
      padding: 6px 11px;
      font-size: 12px;
      white-space: nowrap;
    }
    .layout {
      width: min(1580px, calc(100% - 24px));
      margin: 12px auto;
      min-height: calc(100vh - 94px);
      display: grid;
      grid-template-columns: 286px minmax(0, 1fr) 292px;
      gap: 12px;
    }
    .panel {
      border: 1px solid rgba(96, 165, 250, 0.22);
      border-radius: 8px;
      background: rgba(11, 18, 36, 0.92);
      box-shadow: 0 18px 42px rgba(0, 0, 0, 0.26);
      overflow: hidden;
    }
    .history-panel {
      display: grid;
      grid-template-rows: auto auto 1fr;
      min-height: 0;
    }
    .history-panel.collapsed { grid-template-columns: 48px; width: 48px; }
    .history-panel.collapsed .history-body,
    .history-panel.collapsed .new-chat,
    .history-panel.collapsed .panel-title span { display: none; }
    .panel-title {
      min-height: 48px;
      padding: 12px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      color: #93c5fd;
      font-size: 14px;
      font-weight: 900;
      border-bottom: 1px solid rgba(96, 165, 250, 0.14);
    }
    .history-body {
      padding: 10px;
      overflow-y: auto;
      min-height: 0;
    }
    .history-item {
      padding: 10px;
      margin-bottom: 8px;
      border-radius: 8px;
      border: 1px solid rgba(125, 160, 255, 0.16);
      background: rgba(7, 13, 29, 0.68);
      cursor: pointer;
    }
    .history-item.active {
      border-color: rgba(96, 165, 250, 0.68);
      background: rgba(37, 99, 235, 0.22);
    }
    .history-q { color: #fff; font-size: 13px; font-weight: 800; line-height: 1.35; }
    .history-a {
      margin-top: 5px;
      color: #aebfe8;
      font-size: 12px;
      line-height: 1.4;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }
    .new-chat { margin: 10px; }
    button {
      min-height: 36px;
      border: 0;
      border-radius: 8px;
      background: linear-gradient(135deg, #3155f6, #159ee8);
      color: white;
      cursor: pointer;
      font-weight: 800;
      padding: 0 11px;
      font-size: 13px;
    }
    button:hover { filter: brightness(1.08); }
    button:disabled { opacity: 0.62; cursor: wait; }
    .ghost {
      background: rgba(35, 48, 88, 0.92);
      border: 1px solid rgba(125, 160, 255, 0.24);
    }
    .main-panel {
      display: grid;
      grid-template-rows: auto 1fr auto;
      min-width: 0;
    }
    .collector {
      padding: 12px;
      border-bottom: 1px solid rgba(96, 165, 250, 0.14);
      background: rgba(7, 13, 29, 0.46);
    }
    .collector-grid {
      display: grid;
      grid-template-columns: repeat(5, minmax(120px, 1fr));
      gap: 8px;
    }
    .collect-group {
      min-width: 0;
      padding: 9px;
      border-radius: 8px;
      background: rgba(12, 22, 45, 0.82);
      border: 1px solid rgba(125, 160, 255, 0.14);
    }
    .collect-title {
      margin-bottom: 7px;
      color: #67e8f9;
      font-size: 12px;
      font-weight: 900;
    }
    .chips { display: flex; flex-wrap: wrap; gap: 6px; }
    .chip {
      min-height: 28px;
      padding: 0 8px;
      border-radius: 7px;
      background: rgba(34, 48, 91, 0.96);
      border: 1px solid rgba(125, 160, 255, 0.23);
      color: #edf3ff;
      font-size: 12px;
      font-weight: 700;
    }
    #chat {
      min-height: 520px;
      padding: 16px;
      overflow-y: auto;
    }
    .msg { margin-bottom: 14px; line-height: 1.62; word-break: break-word; }
    .user {
      max-width: 74%;
      margin-left: auto;
      padding: 11px 13px;
      border-radius: 8px;
      background: linear-gradient(135deg, #2563eb, #4f46e5);
      border: 1px solid rgba(191, 219, 254, 0.25);
    }
    .coach-card {
      max-width: 96%;
      padding: 14px;
      border-radius: 8px;
      background: rgba(13, 24, 49, 0.96);
      border: 1px solid rgba(96, 165, 250, 0.24);
    }
    .section-label {
      display: inline-flex;
      margin: 0 0 8px;
      color: #93c5fd;
      font-size: 13px;
      font-weight: 900;
    }
    .summary { margin: 0 0 13px; color: #f8fbff; }
    .points {
      display: grid;
      gap: 8px;
      margin-bottom: 13px;
    }
    .point {
      display: grid;
      grid-template-columns: 88px 1fr;
      gap: 10px;
      padding: 9px 10px;
      border-radius: 8px;
      background: rgba(7, 13, 29, 0.78);
      border: 1px solid rgba(125, 160, 255, 0.16);
    }
    .point-tag { color: #67e8f9; font-size: 12px; font-weight: 900; }
    .point-content { color: #e7efff; font-size: 13px; }
    .details {
      margin: 0 0 13px;
      color: #d9e6ff;
      white-space: pre-wrap;
      font-size: 13px;
    }
    details.react {
      margin-bottom: 13px;
      border-radius: 8px;
      border: 1px solid rgba(45, 212, 191, 0.28);
      background: rgba(8, 47, 54, 0.38);
      overflow: hidden;
    }
    details.react summary {
      cursor: pointer;
      padding: 10px 12px;
      color: #a7f3d0;
      font-weight: 900;
    }
    .react-body { padding: 0 12px 12px; display: grid; gap: 8px; }
    .react-step {
      padding: 9px;
      border-radius: 8px;
      background: rgba(4, 11, 24, 0.7);
      border: 1px solid rgba(45, 212, 191, 0.16);
      color: #dffcf4;
      font-size: 13px;
      line-height: 1.55;
    }
    .react-step strong { color: #67e8f9; }
    .action-row { display: flex; flex-wrap: wrap; gap: 8px; }
    form {
      padding: 13px;
      display: grid;
      grid-template-columns: 1fr 88px;
      gap: 10px;
      border-top: 1px solid rgba(96, 165, 250, 0.14);
    }
    input {
      width: 100%;
      min-height: 40px;
      border: 1px solid rgba(125, 160, 255, 0.26);
      border-radius: 8px;
      background: #080e1f;
      color: #f5f7ff;
      padding: 0 12px;
      outline: none;
      font-size: 14px;
    }
    input:focus { border-color: #60a5fa; box-shadow: 0 0 0 3px rgba(96, 165, 250, 0.13); }
    .side-panel { padding: 12px; overflow: auto; }
    .tool-card {
      padding: 12px;
      margin-bottom: 12px;
      border-radius: 8px;
      background: rgba(7, 13, 29, 0.72);
      border: 1px solid rgba(125, 160, 255, 0.16);
    }
    .tool-title { margin: 0 0 9px; color: #93c5fd; font-size: 14px; font-weight: 900; }
    .tool-grid { display: grid; grid-template-columns: 1fr; gap: 8px; }
    footer { color: #8b9ccf; font-size: 12px; line-height: 1.6; padding-top: 4px; }
    a { color: #93c9ff; }
    @media (max-width: 1200px) {
      .layout { grid-template-columns: 1fr; }
      .collector-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .user, .coach-card { max-width: 100%; }
    }
    @media (max-width: 680px) {
      header { align-items: flex-start; flex-direction: column; }
      .layout { width: calc(100% - 16px); }
      .collector-grid, form, .point { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>电竞AI教练系统 · 王者荣耀</h1>
      <div class="subtitle">历史记忆 + 对局信息采集 + 工具面板 + ReAct 推理可视化</div>
    </div>
    <div class="status">
      <div class="pill">模型：__MODEL_LABEL__</div>
      <div class="pill">API 地址：__BASE_URL__</div>
      <div class="pill">本地运行中</div>
    </div>
  </header>

  <main class="layout">
    <aside class="panel history-panel" id="historyPanel">
      <div class="panel-title"><span>历史对话</span><button class="ghost" id="toggleHistory" type="button">折叠</button></div>
      <button class="new-chat" id="newChat" type="button">新建对话</button>
      <div class="history-body" id="historyList"></div>
    </aside>

    <section class="panel main-panel">
      <div class="collector">
        <div class="collector-grid">
          <div class="collect-group">
            <div class="collect-title">1. 基础信息</div>
            <div class="chips">
              <button class="chip collect" data-mode="fill" type="button">当前英雄：赵云</button>
              <button class="chip collect" data-mode="fill" type="button">位置：打野</button>
              <button class="chip collect" data-mode="fill" type="button">段位：星耀/王者</button>
            </div>
          </div>
          <div class="collect-group">
            <div class="collect-title">2. 对局状态</div>
            <div class="chips">
              <button class="chip collect" data-mode="fill" type="button">阶段：前期</button>
              <button class="chip collect" data-mode="fill" type="button">局势：劣势</button>
              <button class="chip collect" data-mode="fill" type="button">防御塔：外塔掉了</button>
            </div>
          </div>
          <div class="collect-group">
            <div class="collect-title">3. 敌方信息</div>
            <div class="chips">
              <button class="chip collect" data-mode="fill" type="button">敌方核心输出：射手</button>
              <button class="chip collect" data-mode="fill" type="button">敌方控制多</button>
              <button class="chip collect" data-mode="fill" type="button">敌方强开团阵容</button>
            </div>
          </div>
          <div class="collect-group">
            <div class="collect-title">4. 玩家意图</div>
            <div class="chips">
              <button class="chip collect" data-mode="send" type="button">我想打节奏</button>
              <button class="chip collect" data-mode="send" type="button">我想发育</button>
              <button class="chip collect" data-mode="send" type="button">我想运营兵线</button>
              <button class="chip collect" data-mode="send" type="button">我想反打</button>
            </div>
          </div>
          <div class="collect-group">
            <div class="collect-title">5. 当前问题类型</div>
            <div class="chips">
              <button class="chip collect" data-mode="send" type="button">对线问题</button>
              <button class="chip collect" data-mode="send" type="button">团战问题</button>
              <button class="chip collect" data-mode="send" type="button">出装问题</button>
              <button class="chip collect" data-mode="send" type="button">打野节奏问题</button>
            </div>
          </div>
        </div>
      </div>

      <section id="chat">
        <div class="msg coach-card">
          <div class="section-label">教练系统已就绪</div>
          <p class="summary">先用上方按钮补齐对局信息，再提问。我会保留历史对话，并在每次回答中展示 Thought / Action / Observation。</p>
          <details class="react" open>
            <summary>教练思考过程（ReAct Mode）</summary>
            <div class="react-body">
              <div class="react-step"><strong>Thought：</strong>等待玩家补充英雄、位置、局势和敌方信息。</div>
              <div class="react-step"><strong>Action：</strong>根据采集信息选择英雄工具、对局分析或快捷决策。</div>
              <div class="react-step"><strong>Observation：</strong>信息越完整，策略越接近当前真实对局。</div>
            </div>
          </details>
        </div>
      </section>

      <form id="form">
        <input id="message" placeholder="补充对局信息或直接提问，例如：我赵云打野前期劣势，是否可以抓下？" autocomplete="off" />
        <button id="send" type="submit">发送</button>
      </form>
    </section>

    <aside class="panel side-panel">
      <div class="tool-card">
        <h2 class="tool-title">英雄工具箱</h2>
        <div class="tool-grid">
          <button class="ghost tool" type="button">英雄查询</button>
          <button class="ghost tool" type="button">技能说明</button>
          <button class="ghost tool" type="button">出装推荐</button>
        </div>
      </div>
      <div class="tool-card">
        <h2 class="tool-title">对局分析工具</h2>
        <div class="tool-grid">
          <button class="ghost tool" type="button">阵容克制关系</button>
          <button class="ghost tool" type="button">局势判断</button>
          <button class="ghost tool" type="button">胜率倾向分析</button>
        </div>
      </div>
      <div class="tool-card">
        <h2 class="tool-title">快捷操作</h2>
        <div class="tool-grid">
          <button class="ghost tool" type="button">是否可以开团？</button>
          <button class="ghost tool" type="button">是否可以抓人？</button>
          <button class="ghost tool" type="button">如何处理逆风？</button>
        </div>
      </div>
      <footer>接口文档：<a href="/docs">/docs</a><br />健康检查：<a href="/health">/health</a></footer>
    </aside>
  </main>

  <script>
    const chat = document.querySelector("#chat");
    const form = document.querySelector("#form");
    const message = document.querySelector("#message");
    const send = document.querySelector("#send");
    const historyList = document.querySelector("#historyList");
    const historyPanel = document.querySelector("#historyPanel");
    const toggleHistory = document.querySelector("#toggleHistory");
    const newChat = document.querySelector("#newChat");
    const STORE_KEY = "honor_coach_conversations_v2";
    const ACTIVE_KEY = "honor_coach_active_v2";

    function escapeHtml(value) {
      return String(value ?? "").replace(/[&<>"']/g, (char) => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
      }[char]));
    }
    function nowId() { return `conv_${Date.now()}`; }
    function loadConversations() {
      try { return JSON.parse(localStorage.getItem(STORE_KEY) || "[]"); } catch (_error) { return []; }
    }
    function saveConversations(items) { localStorage.setItem(STORE_KEY, JSON.stringify(items)); }
    let conversations = loadConversations();
    let activeId = localStorage.getItem(ACTIVE_KEY) || (conversations[0] && conversations[0].id) || nowId();
    if (!conversations.length) {
      conversations = [{id: activeId, title: "新对话", answer: "等待提问", messages: [], updated_at: Date.now()}];
      saveConversations(conversations);
    }
    function activeConversation() {
      return conversations.find((item) => item.id === activeId) || conversations[0];
    }
    function setActive(id) {
      activeId = id;
      localStorage.setItem(ACTIVE_KEY, id);
      renderHistory();
      renderConversation();
    }
    function summarize(text, fallback) {
      const clean = String(text || fallback || "").replace(/\\s+/g, " ").trim();
      return clean.length > 42 ? `${clean.slice(0, 42)}...` : clean;
    }
    function renderHistory() {
      conversations.sort((a, b) => (b.updated_at || 0) - (a.updated_at || 0));
      historyList.innerHTML = conversations.map((item) => `
        <div class="history-item ${item.id === activeId ? "active" : ""}" data-id="${escapeHtml(item.id)}">
          <div class="history-q">${escapeHtml(item.title || "新对话")}</div>
          <div class="history-a">${escapeHtml(item.answer || "等待 AI 回答")}</div>
        </div>
      `).join("");
      historyList.querySelectorAll(".history-item").forEach((node) => {
        node.onclick = () => setActive(node.dataset.id);
      });
    }
    function renderConversation() {
      const conv = activeConversation();
      const items = conv.messages || [];
      chat.innerHTML = "";
      if (!items.length) {
        chat.innerHTML = `<div class="msg coach-card"><div class="section-label">新对话</div><p class="summary">使用上方信息采集按钮补充局势，或直接提出你的王者荣耀问题。</p></div>`;
        return;
      }
      items.forEach((item) => {
        if (item.role === "user") addUserMessage(item.content, false);
        else addCoachMessage(item.data, false);
      });
      chat.scrollTop = chat.scrollHeight;
    }
    function updateConversation(userText, data) {
      const idx = conversations.findIndex((item) => item.id === activeId);
      const conv = idx >= 0 ? conversations[idx] : {id: activeId, messages: []};
      conv.title = summarize(userText, "新对话");
      conv.answer = summarize(data.summary || data.details || data.answer, "等待 AI 回答");
      conv.updated_at = Date.now();
      conv.messages = [...(conv.messages || []), {role: "user", content: userText}, {role: "assistant", data}].slice(-12);
      conversations[idx >= 0 ? idx : conversations.length] = conv;
      saveConversations(conversations);
      renderHistory();
    }
    function addUserMessage(text, scroll = true) {
      const div = document.createElement("div");
      div.className = "msg user";
      div.textContent = text;
      chat.appendChild(div);
      if (scroll) chat.scrollTop = chat.scrollHeight;
    }
    function reactBlock(trace = {}) {
      return `<details class="react"><summary>教练思考过程（ReAct Mode）</summary>
        <div class="react-body">
          <div class="react-step"><strong>Thought：</strong>${escapeHtml(trace.thought || "分析当前局势、敌方风险点和我方可执行动作。")}</div>
          <div class="react-step"><strong>Action：</strong>${escapeHtml(trace.action || "选择合适策略，并给出下一步操作。")}</div>
          <div class="react-step"><strong>Observation：</strong>${escapeHtml(trace.observation || "根据执行结果继续调整节奏。")}</div>
        </div>
      </details>`;
    }
    function addCoachMessage(data, scroll = true) {
      const card = document.createElement("div");
      card.className = "msg coach-card";
      const points = (data.key_points || []).map((item) => `
        <div class="point"><div class="point-tag">${escapeHtml(item.tag || "要点")}</div><div class="point-content">${escapeHtml(item.content || "")}</div></div>
      `).join("");
      const actions = (data.follow_up_questions || ["是否可以开团？", "是否可以抓人？", "如何处理逆风？"]).slice(0, 5).map((q) =>
        `<button class="chip ask" type="button">${escapeHtml(q)}</button>`
      ).join("");
      card.innerHTML = `
        <div class="section-label">决策摘要</div>
        <p class="summary">${escapeHtml(data.summary || "先判断局势，再选择最稳的下一步。")}</p>
        ${reactBlock(data.react_trace || {})}
        <div class="section-label">核心决策点</div>
        <div class="points">${points}</div>
        <div class="section-label">教练建议</div>
        <div class="details">${escapeHtml(data.details || data.answer || "")}</div>
        <div class="section-label">下一步操作</div>
        <div class="action-row">${actions}</div>
      `;
      chat.appendChild(card);
      card.querySelectorAll(".ask").forEach((button) => button.onclick = () => sendQuestion(button.textContent || ""));
      if (scroll) chat.scrollTop = chat.scrollHeight;
    }
    function appendToInput(text) {
      const current = message.value.trim();
      message.value = current ? `${current}；${text}` : text;
      message.focus();
    }
    async function sendQuestion(text) {
      const value = text.trim();
      if (!value) return;
      addUserMessage(value);
      message.value = "";
      send.disabled = true;
      try {
        const response = await fetch("/api/chat", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({user_id: "honor_user", message: value, game: "王者荣耀"})
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "请求失败");
        addCoachMessage(data);
        updateConversation(value, data);
      } catch (error) {
        const data = {
          summary: "这次请求没打通，请检查后端服务、LLM Provider 和 API Key。",
          key_points: [{tag: "排查", content: error.message}],
          details: `请求失败：${error.message}`,
          follow_up_questions: ["重新发送刚才的问题", "如何检查DeepSeek配置？"],
          react_trace: {thought: "请求链路异常。", action: "检查后端和模型配置。", observation: error.message}
        };
        addCoachMessage(data);
        updateConversation(value, data);
      } finally {
        send.disabled = false;
        message.focus();
      }
    }
    document.querySelectorAll(".collect").forEach((button) => {
      button.onclick = () => {
        const text = button.textContent || "";
        if (button.dataset.mode === "send") sendQuestion(text);
        else appendToInput(text);
      };
    });
    document.querySelectorAll(".tool").forEach((button) => {
      button.onclick = () => sendQuestion(button.textContent || "");
    });
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      sendQuestion(message.value);
    });
    newChat.onclick = () => {
      activeId = nowId();
      conversations.unshift({id: activeId, title: "新对话", answer: "等待提问", messages: [], updated_at: Date.now()});
      localStorage.setItem(ACTIVE_KEY, activeId);
      saveConversations(conversations);
      renderHistory();
      renderConversation();
    };
    toggleHistory.onclick = () => {
      historyPanel.classList.toggle("collapsed");
      toggleHistory.textContent = historyPanel.classList.contains("collapsed") ? "展" : "折叠";
    };
    renderHistory();
    renderConversation();
  </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    """Render the single-page Honor of Kings assistant dashboard."""
    settings = get_settings()
    provider = settings.llm_provider.strip().lower() or "deepseek"
    if provider == "deepseek":
        model_label = f"deepseek / {settings.deepseek_model}"
        base_url = settings.deepseek_base_url
    else:
        model_label = f"{provider} / {settings.ollama_model}"
        base_url = settings.ollama_base_url
    return (
        HTML_TEMPLATE.replace("__MODEL_LABEL__", model_label)
        .replace("__BASE_URL__", base_url)
    )


@app.get("/health")
def health() -> dict[str, str]:
    """Health check kept for existing scripts and docs."""
    return {"status": "ok"}


@app.post("/api/chat", response_model=CompanionChatResponse)
def companion_chat_endpoint(request: CompanionChatRequest) -> CompanionChatResponse:
    """Chat with the 王者荣耀 companion agent."""
    payload = request.model_dump()
    payload["game"] = KING_GAME
    payload.setdefault("user_id", "honor_user")
    result = chat_with_companion(payload)
    return CompanionChatResponse(**result)


@app.get("/api/memory")
def get_memory_endpoint(user_id: str = Query(default="honor_user")) -> dict[str, Any]:
    """Read local JSON player memory."""
    return {"user_id": user_id, "memory": LocalPlayerMemory().get(user_id)}


@app.post("/api/memory")
def post_memory_endpoint(request: PlayerMemoryWriteRequest) -> dict[str, Any]:
    """Write local JSON player memory."""
    memory = update_memory(
        user_id=request.user_id,
        profile={
            "favorite_game": KING_GAME,
            "favorite_character": request.favorite_character,
            "play_mode": request.play_mode,
            "play_style": request.play_style,
            "goal": request.goal,
        },
        note=request.note,
    )
    return {"user_id": request.user_id, "memory": memory}


@app.get("/api/guides")
def guides_endpoint(game: str = KING_GAME, query: str = "") -> dict[str, Any]:
    """Return guide search results from the local 王者荣耀 knowledge base."""
    game = KING_GAME
    if query:
        return guide_search(query=query, game=game, top_k=5)
    guides = [item for item in _load_json(GUIDES_FILE) if game in item.get("game", "")]
    return {"context_items": guides}


@app.post("/api/plan")
def plan_endpoint(request: PlanRequest) -> dict[str, Any]:
    """Generate a deterministic 王者荣耀 task plan without requiring LLM output."""
    return task_plan_tool(
        goal=request.goal,
        game=KING_GAME,
        play_style=request.style,
        available_minutes=request.available_minutes,
    )


@app.post("/api/recommend")
def recommend_endpoint(request: RecommendRequest) -> dict[str, Any]:
    """Generate deterministic 王者荣耀 character and equipment recommendations."""
    return build_recommend(
        game=KING_GAME,
        play_style=request.style,
        favorite_character=request.character,
        current_goal=request.goal,
    )


@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest) -> ChatResponse:
    """Legacy chat endpoint kept for compatibility."""
    if not request.query_text:
        raise HTTPException(status_code=422, detail="message or user_query is required")
    return user_chat(
        user_query=request.query_text,
        user_id=request.user_id,
        game_name=request.game_name,
        task_type=request.task_type,
        game_stage=request.game_stage,
        play_style=request.play_style,
        favorite_character=request.favorite_character,
        current_goal=request.current_goal,
    )


@app.post("/user_chat", response_model=ChatResponse)
def legacy_chat_endpoint(request: ChatRequest) -> ChatResponse:
    """Older endpoint alias kept for existing callers."""
    return chat_endpoint(request)


@app.post("/memory_manage", response_model=MemoryResponse)
def memory_endpoint(request: MemoryRequest) -> MemoryResponse:
    """Legacy Chroma memory endpoint kept for compatibility."""
    ok, related = memory_manage(
        user_id=request.user_id,
        content=request.content,
        operate_type=request.operate_type,
    )
    return MemoryResponse(operate_result=ok, related_memory=related)


@app.post("/tool_invoke", response_model=ToolInvokeResponse)
def tool_endpoint(request: ToolInvokeRequest) -> ToolInvokeResponse:
    """Legacy tool invocation endpoint kept for compatibility."""
    try:
        return ToolInvokeResponse(tool_data=tool_invoke(request.tool_name, request.tool_params))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/get_agent_trace/{trace_id}", response_model=TraceResponse)
def trace_endpoint(trace_id: str) -> TraceResponse:
    """Read a saved legacy agent trace."""
    trace = TraceStore().get(trace_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="trace not found")
    return TraceResponse(**trace)


