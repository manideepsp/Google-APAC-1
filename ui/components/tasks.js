const STATUS_OPTIONS = ["TODO", "IN_PROGRESS", "COMPLETED", "OUT_OF_SCOPE"];

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

export function renderTasks(container, tasks, pendingChanges, onEdit) {
  if (!tasks.length) {
    container.innerHTML = "<p class='text-secondary'>No active tasks yet. Generate a strategy to begin.</p>";
    return;
  }

  container.innerHTML = `
    <div class="table-wrap">
      <table class="tasks-table">
        <thead>
          <tr>
            <th>Task</th>
            <th>Priority</th>
            <th>Day</th>
            <th>Status</th>
            <th>Live</th>
          </tr>
        </thead>
        <tbody>
          ${tasks
            .map((task) => {
              const change = pendingChanges.get(task.uuid) || {};
              const selectedStatus = change.status ?? task.status;
              const selectedLive = change.live ?? Boolean(task.live);

              return `
                <tr data-uuid="${escapeHtml(task.uuid)}">
                  <td>
                    ${escapeHtml(task.task)}
                    <small>${escapeHtml(task.uuid)}</small>
                  </td>
                  <td>${escapeHtml(task.priority)}</td>
                  <td>${escapeHtml(task.day)}</td>
                  <td>
                    <select class="status-select">
                      ${STATUS_OPTIONS.map((opt) => `<option value="${opt}" ${opt === selectedStatus ? "selected" : ""}>${opt}</option>`).join("")}
                    </select>
                  </td>
                  <td>
                    <select class="live-select">
                      <option value="true" ${selectedLive ? "selected" : ""}>true</option>
                      <option value="false" ${!selectedLive ? "selected" : ""}>false</option>
                    </select>
                  </td>
                </tr>
              `;
            })
            .join("")}
        </tbody>
      </table>
    </div>
  `;

  container.querySelectorAll("tbody tr").forEach((row) => {
    const uuid = row.dataset.uuid;
    const statusSelect = row.querySelector(".status-select");
    const liveSelect = row.querySelector(".live-select");

    statusSelect.addEventListener("change", () => {
      onEdit(uuid, { status: statusSelect.value });
    });

    liveSelect.addEventListener("change", () => {
      onEdit(uuid, { live: liveSelect.value === "true" });
    });
  });
}
