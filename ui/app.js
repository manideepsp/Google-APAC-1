import { initChat } from "./components/chat.js";
import { renderTasks } from "./components/tasks.js";
import { renderAnalytics } from "./components/analytics.js";
import { renderHistory } from "./components/history.js";

const state = {
  goalPayload: null,
  tasks: [],
  history: [],
  research: null,
  pendingChanges: new Map(),
  sessionToken: localStorage.getItem("session_token") || "",
  user: null,
};

const els = {
  chatState: document.getElementById("chatState"),
  btnGenerate: document.getElementById("btnGenerate"),
  btnAnalyze: document.getElementById("btnAnalyze"),
  btnRefresh: document.getElementById("btnRefresh"),
  btnLogout: document.getElementById("btnLogout"),
  userBadge: document.getElementById("userBadge"),
  btnSaveChanges: document.getElementById("btnSaveChanges"),
  panelTasks: document.getElementById("panel-tasks"),
  panelAnalytics: document.getElementById("panel-analytics"),
  panelIdeas: document.getElementById("panel-ideas"),
  panelHistory: document.getElementById("panel-history"),
  processingOverlay: document.getElementById("processingOverlay"),
  processingFeed: document.getElementById("processingFeed"),
  tabs: document.getElementById("tabs"),
};

function setChatState(text) {
  els.chatState.textContent = text;
}

function clearSessionAndRedirect() {
  localStorage.removeItem("session_token");
  localStorage.removeItem("user_email");
  window.location.href = "/login.html";
}

function getAuthHeaders(extraHeaders = {}) {
  return {
    "Content-Type": "application/json",
    "X-Session-Token": state.sessionToken,
    ...extraHeaders,
  };
}

function updateSaveButton() {
  const hasChanges = state.pendingChanges.size > 0;
  els.btnSaveChanges.classList.toggle("hidden", !hasChanges);
}

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: getAuthHeaders(options.headers || {}),
    ...options,
  });

  if (res.status === 401) {
    clearSessionAndRedirect();
    throw new Error("Authentication required");
  }

  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Request failed: ${res.status}`);
  }

  return res.json();
}

async function ensureAuthenticated() {
  if (!state.sessionToken) {
    clearSessionAndRedirect();
    return;
  }

  const res = await fetch("/auth/me", {
    headers: getAuthHeaders(),
  });

  if (!res.ok) {
    clearSessionAndRedirect();
    return;
  }

  const data = await res.json();
  state.user = data.user;
  els.userBadge.textContent = data.user?.email || "User";
}

function showProcessing(lines) {
  els.processingFeed.innerHTML = "";
  els.processingOverlay.classList.remove("hidden");

  lines.forEach((line, idx) => {
    setTimeout(() => {
      const el = document.createElement("div");
      el.className = "line";
      el.textContent = `> ${line}`;
      els.processingFeed.appendChild(el);
    }, idx * 450);
  });
}

function hideProcessing() {
  els.processingOverlay.classList.add("hidden");
}

async function refreshData() {
  const [active, history] = await Promise.all([api("/tasks"), api("/tasks/history")]);
  state.tasks = active.tasks || [];
  state.history = history.tasks || [];
}

function renderIdeas(panel, research) {
  const insights = research?.web_insights || [];

  if (!insights.length) {
    panel.innerHTML = "<p class='text-secondary'>No web ideas loaded yet. Generate strategy first.</p>";
    return;
  }

  panel.innerHTML = `
    <div class="ideas-grid">
      ${insights
        .map(
          (item) => `
            <article class="idea-card">
              <h4 class="font-semibold mb-2">${escapeHtml(item.title || "Untitled")}</h4>
              <ul>
                ${(item.ideas || []).slice(0, 3).map((idea) => `<li>${escapeHtml(idea)}</li>`).join("")}
              </ul>
            </article>
          `
        )
        .join("")}
    </div>
  `;
}

function renderAll() {
  renderTasks(els.panelTasks, state.tasks, state.pendingChanges, (uuid, patch) => {
    const previous = state.pendingChanges.get(uuid) || {};
    state.pendingChanges.set(uuid, { ...previous, ...patch });
    updateSaveButton();
  });

  renderAnalytics(els.panelAnalytics, state.research);
  renderIdeas(els.panelIdeas, state.research);
  renderHistory(els.panelHistory, state.history);
  updateSaveButton();
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

async function generateStrategy(payload) {
  state.goalPayload = payload;
  setChatState("Generating");
  showProcessing([
    "Fetching trends...",
    "Analyzing channels...",
    "Finding web opportunities...",
    "Building strategy...",
    "Generating tasks...",
  ]);

  try {
    const data = await api("/goal", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    state.research = data.research || null;
    await refreshData();
    renderAll();
    setChatState("Ready");
    switchTab("tasks");
  } catch (err) {
    setChatState("Error");
    console.error(err);
  } finally {
    hideProcessing();
  }
}

async function analyzeStrategy() {
  if (!state.goalPayload?.channel_id) {
    setChatState("Missing channel id");
    return;
  }

  setChatState("Analyzing");
  showProcessing([
    "Reviewing latest performance...",
    "Replacing outdated tasks...",
    "Syncing board...",
  ]);

  try {
    await api("/analyze", {
      method: "POST",
      body: JSON.stringify({ channel_id: state.goalPayload.channel_id }),
    });

    await refreshData();
    renderAll();
    setChatState("Ready");
    switchTab("tasks");
  } catch (err) {
    setChatState("Error");
    console.error(err);
  } finally {
    hideProcessing();
  }
}

async function saveChanges() {
  if (!state.pendingChanges.size) {
    return;
  }

  setChatState("Saving");

  try {
    for (const [uuid, patch] of state.pendingChanges.entries()) {
      await api("/task/update", {
        method: "POST",
        body: JSON.stringify({ uuid, ...patch }),
      });
    }

    state.pendingChanges.clear();
    await refreshData();
    renderAll();
    setChatState("Ready");
  } catch (err) {
    setChatState("Save failed");
    console.error(err);
  }
}

function switchTab(tabName) {
  const panels = {
    tasks: els.panelTasks,
    analytics: els.panelAnalytics,
    ideas: els.panelIdeas,
    history: els.panelHistory,
  };

  Object.entries(panels).forEach(([name, panel]) => {
    panel.classList.toggle("hidden", name !== tabName);
  });

  [...els.tabs.querySelectorAll(".tab")].forEach((tabBtn) => {
    tabBtn.classList.toggle("is-active", tabBtn.dataset.tab === tabName);
  });
}

function wireTabs() {
  els.tabs.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-tab]");
    if (!button) {
      return;
    }

    switchTab(button.dataset.tab);
  });
}

async function bootstrap() {
  await ensureAuthenticated();

  initChat({
    threadEl: document.getElementById("chatThread"),
    formEl: document.getElementById("chatForm"),
    inputEl: document.getElementById("chatInput"),
    onState: setChatState,
    onSubmit: generateStrategy,
  });

  wireTabs();

  els.btnGenerate.addEventListener("click", () => {
    if (state.goalPayload) {
      generateStrategy(state.goalPayload);
    }
  });

  els.btnAnalyze.addEventListener("click", analyzeStrategy);
  els.btnLogout.addEventListener("click", async () => {
    try {
      await api("/auth/logout", { method: "POST", body: JSON.stringify({}) });
    } catch (err) {
      console.error(err);
    } finally {
      clearSessionAndRedirect();
    }
  });
  els.btnRefresh.addEventListener("click", async () => {
    setChatState("Refreshing");
    await refreshData();
    renderAll();
    setChatState("Ready");
  });
  els.btnSaveChanges.addEventListener("click", saveChanges);

  try {
    await refreshData();
  } catch (err) {
    console.error(err);
  }

  renderAll();
}

bootstrap();
