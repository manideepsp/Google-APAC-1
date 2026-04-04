export function renderHistory(container, tasks) {
  if (!tasks || !tasks.length) {
    container.innerHTML = "<p class='text-secondary'>No task history yet.</p>";
    return;
  }

  const rows = tasks
    .slice(0, 120)
    .map(
      (task) => `
        <article class="history-item">
          <div class="history-meta">${task.updated_at || "-"} | ${task.uuid}</div>
          <p class="mt-1">${task.task}</p>
          <div class="history-meta mt-1">status=${task.status} live=${task.live} day=${task.day} priority=${task.priority}</div>
        </article>
      `
    )
    .join("");

  container.innerHTML = `<section class="history-list">${rows}</section>`;
}
