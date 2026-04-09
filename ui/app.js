import { initChat } from "./components/chat.js?v=20260408d";
import { renderAnalytics } from "./components/analytics.js?v=20260408d";
import {
  renderArchiveRuns,
  renderIdeasRuns,
  renderWorkspaceRuns,
  summarizeRunsForAnalytics,
} from "./components/runs.js?v=20260408d";

const state = {
  sessionToken: localStorage.getItem("session_token") || "",
  user: null,
  activeChannelId: "",
  channelOptions: [],
  goalParams: {
    Goal: "",
    Audience: "",
    Budget: "",
    Timeline: "",
    "Content Type": "",
    "Channel ID": "",
  },
  goalConversation: [],
  runs: [],
  modifications: [],
  lastError: "",
  isGenerating: false,
  isAnalyzing: false,
};

const els = {
  chatState: document.getElementById("chatState"),
  btnAnalyze: document.getElementById("btnAnalyze"),
  btnRefresh: document.getElementById("btnRefresh"),
  btnLogout: document.getElementById("btnLogout"),
  userBadge: document.getElementById("userBadge"),
  panelTasks: document.getElementById("panel-tasks"),
  panelAnalytics: document.getElementById("panel-analytics"),
  panelIdeas: document.getElementById("panel-ideas"),
  panelArchive: document.getElementById("panel-archive"),
  processingOverlay: document.getElementById("processingOverlay"),
  processingFeed: document.getElementById("processingFeed"),
  tabs: document.getElementById("tabs"),
  activeChannelSelect: document.getElementById("activeChannelSelect"),
  channelInput: document.getElementById("channelInput"),
  btnSetChannel: document.getElementById("btnSetChannel"),
  goalParamsPanel: document.getElementById("goalParamsPanel"),
  btnAddParam: document.getElementById("btnAddParam"),
  btnGenerateFromParams: document.getElementById("btnGenerateFromParams"),
  toastStack: document.getElementById("toastStack"),
};

let toastSeed = 0;

function setChatState(text) {
  els.chatState.textContent = text;
}

function clearSessionAndRedirect() {
  localStorage.removeItem("session_token");
  localStorage.removeItem("user_email");
  window.location.href = "/login.html";
}

function showToast(kind, title, message, { timeout = 3500 } = {}) {
  if (!els.toastStack) {
    return;
  }

  toastSeed += 1;
  const id = `toast-${Date.now()}-${toastSeed}`;
  const toast = document.createElement("article");
  toast.id = id;
  toast.className = `toast toast-${kind}`;
  toast.setAttribute("role", kind === "error" ? "alert" : "status");

  const safeTitle = escapeHtml(title || "Update");
  const safeMessage = escapeHtml(message || "Done");

  toast.innerHTML = `
    <p class="toast-title">${safeTitle}</p>
    <p class="toast-message">${safeMessage}</p>
  `;

  els.toastStack.appendChild(toast);

  setTimeout(() => {
    toast.classList.add("toast-exit");
    setTimeout(() => {
      toast.remove();
    }, 210);
  }, timeout);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function getAuthHeaders(extraHeaders = {}) {
  return {
    "Content-Type": "application/json",
    "X-Session-Token": state.sessionToken,
    ...extraHeaders,
  };
}

function getErrorMessage(err) {
  if (!err) {
    return "Unknown error";
  }

  const raw = String(err.message || err);
  try {
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed.detail === "string") {
      return parsed.detail;
    }
  } catch {
    // Ignore parse errors for plain text responses.
  }
  return raw;
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
    const errorCode = res.headers.get("X-Error-Code") || "";
    const retryAfter = res.headers.get("Retry-After") || "";

    if (errorCode === "GEMINI_QUOTA_EXHAUSTED") {
      const retryText = retryAfter ? ` Retry after ~${retryAfter}s.` : "";
      throw new Error(`GEMINI_QUOTA_EXHAUSTED: Gemini quota is exhausted.${retryText}`);
    }

    throw new Error(text || `Request failed: ${res.status}`);
  }

  return res.json();
}

async function ensureAuthenticated() {
  if (!state.sessionToken) {
    clearSessionAndRedirect();
    return;
  }

  const data = await api("/auth/me");
  state.user = data.user;
  els.userBadge.textContent = data.user?.email || "User";
  showToast("success", "Signed in", `Welcome ${data.user?.email || "User"}`, { timeout: 2200 });
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
    }, idx * 400);
  });
}

function hideProcessing() {
  els.processingOverlay.classList.add("hidden");
}

function syncActionButtonState() {
  const locked = state.isGenerating || state.isAnalyzing;
  els.btnGenerateFromParams.disabled = locked;
  els.btnAnalyze.disabled = locked;
}

function normalizeGoalParams(goalParams) {
  const normalized = {};
  for (const [key, value] of Object.entries(goalParams || {})) {
    const k = String(key || "").trim();
    const v = String(value || "").trim();
    if (k && v) {
      normalized[k] = v;
    }
  }

  if (!normalized.Goal && state.goalParams.Goal) {
    normalized.Goal = String(state.goalParams.Goal).trim();
  }

  return normalized;
}

function goalTextFromParams(goalParams) {
  const params = normalizeGoalParams(goalParams);
  if (params.Goal) {
    return params.Goal;
  }
  const parts = Object.entries(params).map(([k, v]) => `${k}: ${v}`);
  return parts.join("; ");
}

function selectedChannelOrGoalChannel() {
  const fromState = String(state.activeChannelId || "").trim();
  if (fromState) {
    return fromState;
  }

  return String(state.goalParams["Channel ID"] || "").trim();
}

async function refreshChannels() {
  const result = await api("/channels");
  const channels = result.channels || [];
  const merged = new Set([state.activeChannelId, state.goalParams["Channel ID"], ...channels].filter(Boolean));
  state.channelOptions = [...merged];

  if (!state.activeChannelId && state.channelOptions.length) {
    state.activeChannelId = state.channelOptions[0];
  }

  els.activeChannelSelect.innerHTML = state.channelOptions.length
    ? state.channelOptions.map((channelId) => `<option value="${escapeHtml(channelId)}">${escapeHtml(channelId)}</option>`).join("")
    : "<option value=''>No channel selected</option>";

  if (state.activeChannelId) {
    els.activeChannelSelect.value = state.activeChannelId;
  }
}

function renderGoalParams() {
  const entries = Object.entries(state.goalParams || {});

  els.goalParamsPanel.innerHTML = `
    <table class="goal-param-table">
      <tbody>
        ${entries
          .map(
            ([key, value]) => `
              <tr>
                <td><input class="param-input" data-role="param-key" data-key="${escapeHtml(key)}" value="${escapeHtml(key)}" /></td>
                <td><input class="param-input" data-role="param-value" data-key="${escapeHtml(key)}" value="${escapeHtml(value)}" /></td>
              </tr>
            `
          )
          .join("")}
      </tbody>
    </table>
  `;

  els.goalParamsPanel.querySelectorAll("input[data-role='param-value']").forEach((input) => {
    input.addEventListener("change", () => {
      const key = input.dataset.key;
      if (!key) {
        return;
      }
      state.goalParams[key] = input.value;
    });
  });

  els.goalParamsPanel.querySelectorAll("input[data-role='param-key']").forEach((input) => {
    input.addEventListener("change", () => {
      const oldKey = input.dataset.key;
      const newKey = String(input.value || "").trim();
      if (!oldKey || !newKey || oldKey === newKey) {
        input.value = oldKey || newKey;
        return;
      }

      const value = state.goalParams[oldKey];
      delete state.goalParams[oldKey];
      state.goalParams[newKey] = value;
      renderGoalParams();
    });
  });
}

function splitRuns() {
  const workspaceRuns = [];
  const archiveRuns = [];

  for (const run of state.runs) {
    const activeTasks = (run.tasks || []).filter((task) => task.live && task.status !== "COMPLETED");
    const archivedTasks = (run.tasks || []).filter((task) => !task.live || task.status === "COMPLETED");

    if (activeTasks.length) {
      workspaceRuns.push(run);
    }
    if (archivedTasks.length) {
      archiveRuns.push(run);
    }
  }

  return { workspaceRuns, archiveRuns };
}

function renderAll() {
  const { workspaceRuns, archiveRuns } = splitRuns();

  renderWorkspaceRuns(els.panelTasks, workspaceRuns, state.modifications);
  renderArchiveRuns(els.panelArchive, archiveRuns, state.modifications);
  renderIdeasRuns(els.panelIdeas, state.runs);

  const researchForAnalytics = summarizeRunsForAnalytics(state.runs);
  renderAnalytics(els.panelAnalytics, researchForAnalytics);

  if (state.lastError) {
    const errorHtml = `<div class="list-card"><h3 class="font-semibold">Latest Error</h3><p class="text-secondary text-sm mt-1">${escapeHtml(state.lastError)}</p></div>`;
    els.panelAnalytics.insertAdjacentHTML("afterbegin", errorHtml);
  }

  renderGoalParams();
}

function switchTab(tabName) {
  const panels = {
    tasks: els.panelTasks,
    analytics: els.panelAnalytics,
    ideas: els.panelIdeas,
    archive: els.panelArchive,
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

async function refreshRuns() {
  const channel = selectedChannelOrGoalChannel();

  if (!channel) {
    state.runs = [];
    return;
  }

  const query = `?channel_id=${encodeURIComponent(channel)}`;
  const data = await api(`/runs${query}`);
  state.runs = data.runs || [];

  if (state.runs.length) {
    state.goalParams = {
      ...state.goalParams,
      ...(state.runs[0].goal_params || {}),
    };
  }
}

async function refreshModifications() {
  const channel = selectedChannelOrGoalChannel();
  if (!channel) {
    state.modifications = [];
    return;
  }

  const query = `?channel_id=${encodeURIComponent(channel)}&limit=200`;
  const data = await api(`/tasks/modifications${query}`);
  state.modifications = data.modifications || [];
}

async function refreshWorkspace() {
  await refreshChannels();
  await Promise.all([refreshRuns(), refreshModifications()]);
}

async function assistantTurn(message, history) {
  const result = await api("/goal/assistant", {
    method: "POST",
    body: JSON.stringify({
      message,
      history,
      goal_params: normalizeGoalParams(state.goalParams),
      channel_id: selectedChannelOrGoalChannel() || null,
    }),
  });

  state.goalConversation = history;
  state.goalParams = {
    ...state.goalParams,
    ...(result.goal_params || {}),
  };

  const channelId = String(result?.goal_params?.["Channel ID"] || "").trim();
  if (channelId) {
    state.activeChannelId = channelId;
  }

  await refreshChannels();
  renderGoalParams();
  return result;
}

async function generateStrategyFromParams() {
  if (state.isGenerating || state.isAnalyzing) {
    return;
  }

  const goalParams = normalizeGoalParams(state.goalParams);
  const goal = goalTextFromParams(goalParams);
  const channelId = selectedChannelOrGoalChannel() || null;

  if (!goal) {
    setChatState("Missing goal");
    showToast("warning", "Goal missing", "Add Goal parameter before generating strategy.");
    return;
  }

  setChatState("Generating");
  state.isGenerating = true;
  syncActionButtonState();
  showProcessing([
    "Refining parameters...",
    "Fetching trends...",
    "Analyzing channels...",
    "Building strategy run...",
    "Generating tasks...",
  ]);

  try {
    await api("/goal", {
      method: "POST",
      body: JSON.stringify({
        goal,
        goal_params: goalParams,
        channel_id: channelId,
      }),
    });

    state.lastError = "";
    await refreshWorkspace();
    renderAll();
    setChatState("Ready");
    switchTab("tasks");
    showToast("success", "Strategy generated", "New run and tasks are ready.");
  } catch (err) {
    state.lastError = getErrorMessage(err);
    setChatState("Error");
    renderAll();
    showToast("error", "Generate failed", state.lastError);
  } finally {
    hideProcessing();
    state.isGenerating = false;
    syncActionButtonState();
  }
}

async function analyzeStrategy() {
  if (state.isGenerating || state.isAnalyzing) {
    return;
  }

  const goalParams = normalizeGoalParams(state.goalParams);
  const channelId = selectedChannelOrGoalChannel() || null;

  if (!channelId) {
    setChatState("Missing channel id");
    showToast("warning", "Channel missing", "Set a channel ID before running analysis.");
    return;
  }

  setChatState("Analyzing");
  state.isAnalyzing = true;
  syncActionButtonState();
  showProcessing([
    "Loading active workspace tasks...",
    "Applying reflection model...",
    "Updating run traceability...",
  ]);

  try {
    await api("/analyze", {
      method: "POST",
      body: JSON.stringify({
        goal: goalTextFromParams(goalParams),
        goal_params: goalParams,
        channel_id: channelId,
      }),
    });

    state.lastError = "";
    await refreshWorkspace();
    renderAll();
    setChatState("Ready");
    showToast("success", "Analysis complete", "Strategy updated with latest reflection insights.");
  } catch (err) {
    state.lastError = getErrorMessage(err);
    setChatState("Error");
    renderAll();
    showToast("error", "Analyze failed", state.lastError);
  } finally {
    hideProcessing();
    state.isAnalyzing = false;
    syncActionButtonState();
  }
}

async function moveTask(uuid, target) {
  try {
    const result = await api("/task/move", {
      method: "POST",
      body: JSON.stringify({ uuid, target }),
    });
    await Promise.all([refreshRuns(), refreshModifications()]);
    renderAll();
    const changed = (result?.changes || []).map((item) => item.field).join(", ");
    const details = target === "archive" ? "Task moved to Archive." : "Task moved to Tasks.";
    showToast("success", "Task moved", changed ? `${details} Updated: ${changed}.` : details);
  } catch (err) {
    const message = getErrorMessage(err);
    state.lastError = message;
    renderAll();
    showToast("error", "Move failed", message);
  }
}

async function saveTaskEdits(uuid, rowElement) {
  const prioritySelect = rowElement?.querySelector("select[data-field='priority']");
  const statusSelect = rowElement?.querySelector("select[data-field='status']");
  const liveSelect = rowElement?.querySelector("select[data-field='live']");

  if (!prioritySelect || !statusSelect || !liveSelect) {
    showToast("error", "Save failed", "Task edit controls were not found in the row.");
    return;
  }

  const payload = {
    uuid,
    priority: prioritySelect.value,
    status: statusSelect.value,
    live: liveSelect.value === "true",
  };

  try {
    const result = await api("/task/update", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    await Promise.all([refreshRuns(), refreshModifications()]);
    renderAll();

    const fields = (result?.changes || []).map((item) => item.field).filter(Boolean);
    const detail = fields.length
      ? `Updated fields: ${fields.join(", ")}.`
      : "No field changes detected.";
    showToast("success", "Task saved", detail);
  } catch (err) {
    const message = getErrorMessage(err);
    state.lastError = message;
    renderAll();
    showToast("error", "Save failed", message);
  }
}

function wireRunActions() {
  document.body.addEventListener("click", async (event) => {
    const btn = event.target.closest("button[data-action][data-uuid]");
    if (!btn) {
      return;
    }

    const uuid = btn.dataset.uuid;
    const action = btn.dataset.action;

    if (action === "save-task") {
      const row = btn.closest("tr[data-uuid]");
      await saveTaskEdits(uuid, row);
    } else if (action === "move-archive") {
      await moveTask(uuid, "archive");
    } else if (action === "move-tasks") {
      await moveTask(uuid, "tasks");
    }
  });
}

async function applyChannelInput() {
  const raw = String(els.channelInput.value || "").trim();
  if (!raw) {
    showToast("warning", "Channel input empty", "Paste a channel ID or channel URL first.");
    return;
  }

  try {
    const parsed = await api("/channel/parse", {
      method: "POST",
      body: JSON.stringify({ value: raw }),
    });

    const channelId = parsed.channel_id || raw;
    state.activeChannelId = channelId;
    state.goalParams["Channel ID"] = channelId;
    await refreshWorkspace();
    renderAll();
    setChatState(parsed.valid ? "Channel set" : "Using raw channel value");
    showToast("success", "Channel updated", parsed.valid ? "Valid channel parsed and applied." : "Using raw channel value.");
  } catch (err) {
    state.lastError = getErrorMessage(err);
    setChatState("Channel parse failed");
    renderAll();
    showToast("error", "Channel parse failed", state.lastError);
  }
}

function wireChannelControls() {
  els.btnSetChannel.addEventListener("click", applyChannelInput);

  els.activeChannelSelect.addEventListener("change", async () => {
    state.activeChannelId = els.activeChannelSelect.value;
    if (state.activeChannelId) {
      state.goalParams["Channel ID"] = state.activeChannelId;
    }
    try {
      await refreshRuns();
      renderAll();
      showToast("success", "Channel switched", `Active channel: ${state.activeChannelId || "none"}`);
    } catch (err) {
      const message = getErrorMessage(err);
      state.lastError = message;
      renderAll();
      showToast("error", "Channel switch failed", message);
    }
  });
}

function wireGoalParamControls() {
  els.btnAddParam.addEventListener("click", () => {
    let idx = 1;
    while (state.goalParams[`Custom ${idx}`]) {
      idx += 1;
    }
    state.goalParams[`Custom ${idx}`] = "";
    renderGoalParams();
  });

  els.btnGenerateFromParams.addEventListener("click", generateStrategyFromParams);
}

async function bootstrap() {
  try {
    await ensureAuthenticated();
  } catch (err) {
    clearSessionAndRedirect();
    return;
  }

  initChat({
    threadEl: document.getElementById("chatThread"),
    formEl: document.getElementById("chatForm"),
    inputEl: document.getElementById("chatInput"),
    onState: setChatState,
    onUserMessage: assistantTurn,
    onToast: showToast,
  });

  wireTabs();
  wireRunActions();
  wireChannelControls();
  wireGoalParamControls();

  els.btnAnalyze.addEventListener("click", analyzeStrategy);
  els.btnRefresh.addEventListener("click", async () => {
    setChatState("Refreshing");
    try {
      await refreshWorkspace();
      renderAll();
      setChatState("Ready");
      showToast("success", "Refreshed", "Workspace data reloaded.");
    } catch (err) {
      const message = getErrorMessage(err);
      state.lastError = message;
      renderAll();
      setChatState("Error");
      showToast("error", "Refresh failed", message);
    }
  });

  els.btnLogout.addEventListener("click", async () => {
    try {
      await api("/auth/logout", { method: "POST", body: JSON.stringify({}) });
    } catch {
      // best-effort logout
    }
    clearSessionAndRedirect();
  });

  try {
    await refreshWorkspace();
  } catch (err) {
    state.lastError = getErrorMessage(err);
    showToast("error", "Initial load issue", state.lastError);
  }

  renderAll();
  syncActionButtonState();
}

bootstrap();
