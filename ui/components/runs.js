function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function sanitizeUrl(value) {
  const url = String(value || "").trim();
  if (!url) {
    return "";
  }
  return url.startsWith("http://") || url.startsWith("https://") ? url : "";
}

const STATUS_OPTIONS = ["TODO", "IN_PROGRESS", "COMPLETED", "OUT_OF_SCOPE"];
const PRIORITY_OPTIONS = ["High", "Medium", "Low"];

function renderSelectOptions(values, selectedValue) {
  const normalized = String(selectedValue ?? "");
  return values
    .map((value) => {
      const selected = value === normalized ? "selected" : "";
      return `<option value="${escapeHtml(value)}" ${selected}>${escapeHtml(value)}</option>`;
    })
    .join("");
}

function buildLatestModificationMap(modifications) {
  const map = {};
  for (const mod of modifications || []) {
    const taskUuid = String(mod?.task_uuid || "").trim();
    if (!taskUuid || map[taskUuid]) {
      continue;
    }
    map[taskUuid] = mod;
  }
  return map;
}

function modificationSummary(modification) {
  if (!modification) {
    return "No manual modifications yet";
  }

  const field = String(modification.field_name || "field");
  const before = String(modification.previous_value || "-");
  const after = String(modification.new_value || "-");
  const action = String(modification.action || "update");
  const timestamp = formatDate(modification.modified_at);
  return `${action}: ${field} ${before} -> ${after} @ ${timestamp}`;
}

function renderRecentModifications(modifications) {
  const items = (modifications || []).slice(0, 10);
  if (!items.length) {
    return "";
  }

  return `
    <section class="list-card modifications-card">
      <h3 class="font-semibold">Recent Modifications</h3>
      <ul class="mod-feed-list">
        ${items
          .map((mod) => {
            const contextTask = String(mod?.context?.task || "").trim();
            const taskLabel = contextTask || `Task ${String(mod.task_uuid || "").slice(0, 8)}`;
            const summary = `${String(mod.action || "update")} ${String(mod.field_name || "field")}: ${String(mod.previous_value || "-")} -> ${String(mod.new_value || "-")}`;
            return `<li><span class="mod-feed-time">${escapeHtml(formatDate(mod.modified_at))}</span> <strong>${escapeHtml(taskLabel)}</strong> <span class="text-secondary">${escapeHtml(summary)}</span></li>`;
          })
          .join("")}
      </ul>
    </section>
  `;
}

function inlineMarkdown(value) {
  let text = escapeHtml(value || "");

  text = text.replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, (_m, label, rawUrl) => {
    const safeUrl = sanitizeUrl(rawUrl);
    if (!safeUrl) {
      return label;
    }
    return `<a class="table-link" href="${escapeHtml(safeUrl)}" target="_blank" rel="noreferrer noopener">${label}</a>`;
  });

  text = text.replace(/`([^`]+)`/g, "<code>$1</code>");
  text = text.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  text = text.replace(/\*([^*]+)\*/g, "<em>$1</em>");

  return text;
}

function markdownToHtml(markdownText) {
  const lines = String(markdownText || "").replace(/\r\n/g, "\n").split("\n");
  const html = [];
  let activeList = null;

  const closeList = () => {
    if (activeList) {
      html.push(`</${activeList}>`);
      activeList = null;
    }
  };

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) {
      closeList();
      continue;
    }

    const heading = line.match(/^(#{1,6})\s+(.+)$/);
    if (heading) {
      closeList();
      const level = Math.min(6, heading[1].length);
      html.push(`<h${level} class="md-h${level}">${inlineMarkdown(heading[2])}</h${level}>`);
      continue;
    }

    const unordered = line.match(/^[-*]\s+(.+)$/);
    if (unordered) {
      if (activeList !== "ul") {
        closeList();
        html.push("<ul>");
        activeList = "ul";
      }
      html.push(`<li>${inlineMarkdown(unordered[1])}</li>`);
      continue;
    }

    const ordered = line.match(/^\d+\.\s+(.+)$/);
    if (ordered) {
      if (activeList !== "ol") {
        closeList();
        html.push("<ol>");
        activeList = "ol";
      }
      html.push(`<li>${inlineMarkdown(ordered[1])}</li>`);
      continue;
    }

    closeList();
    html.push(`<p>${inlineMarkdown(line)}</p>`);
  }

  closeList();
  return html.join("");
}

function formatNumber(value) {
  const num = Number(value || 0);
  if (!Number.isFinite(num)) {
    return "0";
  }
  return num.toLocaleString();
}

function formatDate(value) {
  if (!value) {
    return "-";
  }
  try {
    return new Date(value).toLocaleString();
  } catch {
    return String(value);
  }
}

function goalChips(goalParams) {
  const entries = Object.entries(goalParams || {}).filter(([k, v]) => String(k).trim() && String(v).trim());
  if (!entries.length) {
    return "<p class='trace-note'>No goal parameters recorded for this run.</p>";
  }

  return `
    <div class="param-chip-grid">
      ${entries
        .map(([key, value]) => `<span class="param-chip">${escapeHtml(key)}: ${escapeHtml(value)}</span>`)
        .join("")}
    </div>
  `;
}

function strategySummary(run, { collapsible = true } = {}) {
  const text = String(run?.research?.insights || "").trim();
  if (!text) {
    return "<p class='trace-note'>No strategy summary captured for this run.</p>";
  }

  const markdownHtml = markdownToHtml(text);

  if (collapsible) {
    return `
      <details class="summary-details">
        <summary>Strategy Summary (Click to expand)</summary>
        <div class="summary-markdown">${markdownHtml}</div>
      </details>
    `;
  }

  return `
    <section class="summary-block">
      <h4>Strategy Summary</h4>
      <div class="summary-markdown">${markdownHtml}</div>
    </section>
  `;
}

function runHeader(run, idx) {
  const goal = String(run.goal || run.goal_params?.Goal || "").trim() || "Untitled Goal";
  const goalLabel = `Run ${idx + 1}: ${goal}`;
  const metaText = `${String(run.channel_id || "no-channel")} | ${formatDate(run.created_at)}`;
  return `
    <summary>
      <span class="run-title" data-tooltip="${escapeHtml(goalLabel)}">${escapeHtml(goalLabel)}</span>
      <span class="run-meta" data-tooltip="${escapeHtml(metaText)}">${escapeHtml(metaText)}</span>
    </summary>
  `;
}

function workspaceTaskRows(tasks, latestModificationByTask) {
  if (!tasks.length) {
    return `<tr><td colspan="7" class="text-secondary">No active tasks for this run.</td></tr>`;
  }

  return tasks
    .map(
      (task) => {
        const taskUuid = String(task.uuid || "");
        const latestTrace = latestModificationByTask[taskUuid];
        const traceSummary = modificationSummary(latestTrace);

        return `
        <tr data-uuid="${escapeHtml(taskUuid)}">
          <td>${escapeHtml(task.task)}</td>
          <td>
            <select class="task-edit-select priority-select" data-field="priority" data-uuid="${escapeHtml(taskUuid)}">
              ${renderSelectOptions(PRIORITY_OPTIONS, task.priority)}
            </select>
          </td>
          <td>${escapeHtml(task.day)}</td>
          <td>
            <select class="task-edit-select status-select" data-field="status" data-uuid="${escapeHtml(taskUuid)}">
              ${renderSelectOptions(STATUS_OPTIONS, task.status)}
            </select>
          </td>
          <td>
            <select class="task-edit-select live-select" data-field="live" data-uuid="${escapeHtml(taskUuid)}">
              <option value="true" ${task.live ? "selected" : ""}>true</option>
              <option value="false" ${task.live ? "" : "selected"}>false</option>
            </select>
          </td>
          <td>
            <div>${escapeHtml(formatDate(task.updated_at))}</div>
            <div class="trace-note" data-tooltip="${escapeHtml(traceSummary)}">trace=${escapeHtml(traceSummary)}</div>
            <div class="trace-note">origin=${escapeHtml(task.origin_run_id || task.run_id || "-")}</div>
          </td>
          <td>
            <div class="task-action-stack">
              <button class="mini-btn" data-action="save-task" data-uuid="${escapeHtml(taskUuid)}" data-tooltip="Save priority/status/live changes">Save</button>
              <button class="mini-btn" data-action="move-archive" data-uuid="${escapeHtml(taskUuid)}" data-tooltip="Move this task to Archive">Move to Archive</button>
            </div>
          </td>
        </tr>
      `;
      }
    )
    .join("");
}

function archiveTaskRows(tasks, latestModificationByTask) {
  if (!tasks.length) {
    return `<tr><td colspan="7" class="text-secondary">No archived tasks for this run.</td></tr>`;
  }

  return tasks
    .map(
      (task) => {
        const taskUuid = String(task.uuid || "");
        const latestTrace = latestModificationByTask[taskUuid];
        const traceSummary = modificationSummary(latestTrace);

        return `
        <tr data-uuid="${escapeHtml(taskUuid)}">
          <td>${escapeHtml(task.task)}</td>
          <td>
            <select class="task-edit-select priority-select" data-field="priority" data-uuid="${escapeHtml(taskUuid)}">
              ${renderSelectOptions(PRIORITY_OPTIONS, task.priority)}
            </select>
          </td>
          <td>${escapeHtml(task.day)}</td>
          <td>
            <select class="task-edit-select status-select" data-field="status" data-uuid="${escapeHtml(taskUuid)}">
              ${renderSelectOptions(STATUS_OPTIONS, task.status)}
            </select>
          </td>
          <td>
            <select class="task-edit-select live-select" data-field="live" data-uuid="${escapeHtml(taskUuid)}">
              <option value="true" ${task.live ? "selected" : ""}>true</option>
              <option value="false" ${task.live ? "" : "selected"}>false</option>
            </select>
          </td>
          <td>
            <div>${escapeHtml(formatDate(task.updated_at))}</div>
            <div class="trace-note" data-tooltip="${escapeHtml(traceSummary)}">trace=${escapeHtml(traceSummary)}</div>
            <div class="trace-note">origin=${escapeHtml(task.origin_run_id || task.run_id || "-")}</div>
          </td>
          <td>
            <div class="task-action-stack">
              <button class="mini-btn" data-action="save-task" data-uuid="${escapeHtml(taskUuid)}" data-tooltip="Save priority/status/live changes">Save</button>
              <button class="mini-btn" data-action="move-tasks" data-uuid="${escapeHtml(taskUuid)}" data-tooltip="Move this task back to active Tasks">Move to Tasks</button>
            </div>
          </td>
        </tr>
      `;
      }
    )
    .join("");
}

function renderTaskTable(rowsHtml, modeLabel) {
  return `
    <div class="table-wrap">
      <table class="tasks-table insights-table">
        <thead>
          <tr>
            <th>Task</th>
            <th>Priority</th>
            <th>Day</th>
            <th>Status</th>
            <th>Live</th>
            <th>Updated</th>
            <th>${modeLabel}</th>
          </tr>
        </thead>
        <tbody>
          ${rowsHtml}
        </tbody>
      </table>
    </div>
  `;
}

function ideasRows(webInsights) {
  if (!webInsights.length) {
    return `<tr><td colspan="4" class="text-secondary">No ideas captured for this run.</td></tr>`;
  }

  return webInsights
    .map((item) => {
      const url = String(item.url || "").trim();
      const hasUrl = url.startsWith("http://") || url.startsWith("https://");
      const title = escapeHtml(item.title || "Untitled");
      const titleHtml = hasUrl
        ? `<a class="table-link" href="${escapeHtml(url)}" target="_blank" rel="noreferrer noopener">${title}</a>`
        : title;
      const summary = escapeHtml(item.summary || (item.ideas || []).slice(0, 2).join(" | ") || "-");
      const ideasText = escapeHtml((item.ideas || []).slice(0, 4).join(" | ") || "-");
      const source = hasUrl
        ? `<a class="table-link" href="${escapeHtml(url)}" target="_blank" rel="noreferrer noopener">Open source</a>`
        : "-";

      return `
        <tr>
          <td>${titleHtml}</td>
          <td class="summary-cell" data-tooltip="${summary}"><span class="summary-truncate">${summary}</span></td>
          <td data-tooltip="${ideasText}"><span class="summary-truncate">${ideasText}</span></td>
          <td>${source}</td>
        </tr>
      `;
    })
    .join("");
}

export function renderWorkspaceRuns(container, runs, modifications = []) {
  const latestModificationByTask = buildLatestModificationMap(modifications);
  const rows = (runs || []).map((run, idx) => {
    const tasks = (run.tasks || []).filter((task) => task.live && task.status !== "COMPLETED");

    return `
      <details class="run-block" ${idx === 0 ? "open" : ""}>
        ${runHeader(run, idx)}
        <div class="run-body">
          ${goalChips(run.goal_params || {})}
          ${strategySummary(run)}
          ${renderTaskTable(workspaceTaskRows(tasks, latestModificationByTask), "Actions")}
        </div>
      </details>
    `;
  });

  container.innerHTML = rows.length
    ? `${renderRecentModifications(modifications)}<section class="run-stack">${rows.join("")}</section>`
    : "<p class='text-secondary'>No workspace runs yet. Build a goal and generate strategy.</p>";
}

export function renderArchiveRuns(container, runs, modifications = []) {
  const latestModificationByTask = buildLatestModificationMap(modifications);
  const blocks = (runs || [])
    .map((run, idx) => {
      const archived = (run.tasks || []).filter((task) => !task.live || task.status === "COMPLETED");
      if (!archived.length) {
        return "";
      }

      return `
        <details class="run-block" ${idx === 0 ? "open" : ""}>
          ${runHeader(run, idx)}
          <div class="run-body">
            ${goalChips(run.goal_params || {})}
            ${strategySummary(run, { collapsible: true })}
            ${renderTaskTable(archiveTaskRows(archived, latestModificationByTask), "Actions")}
          </div>
        </details>
      `;
    })
    .filter(Boolean);

  container.innerHTML = blocks.length
    ? `<section class="run-stack">${blocks.join("")}</section>`
    : "<p class='text-secondary'>No archived runs yet.</p>";
}

export function renderIdeasRuns(container, runs) {
  const blocks = (runs || []).map((run, idx) => {
    const webInsights = run?.research?.web_insights || [];

    return `
      <details class="run-block" ${idx === 0 ? "open" : ""}>
        ${runHeader(run, idx)}
        <div class="run-body">
          ${goalChips(run.goal_params || {})}
          ${strategySummary(run)}
          <div class="table-wrap">
            <table class="tasks-table insights-table">
              <thead>
                <tr>
                  <th>Idea Title</th>
                  <th>Summary</th>
                  <th>Key Ideas</th>
                  <th>Source</th>
                </tr>
              </thead>
              <tbody>
                ${ideasRows(webInsights)}
              </tbody>
            </table>
          </div>
        </div>
      </details>
    `;
  });

  container.innerHTML = blocks.length
    ? `<section class="run-stack">${blocks.join("")}</section>`
    : "<p class='text-secondary'>No ideas history yet.</p>";
}

export function summarizeRunsForAnalytics(runs) {
  const latest = (runs || [])[0] || null;
  if (!latest) {
    return null;
  }
  return latest.research || null;
}
