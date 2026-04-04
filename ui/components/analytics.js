function renderList(title, items) {
  if (!items || !items.length) {
    return `
      <section class="list-card">
        <h3 class="font-semibold">${title}</h3>
        <p class="text-secondary text-sm mt-1">No data yet.</p>
      </section>
    `;
  }

  return `
    <section class="list-card">
      <h3 class="font-semibold">${title}</h3>
      <ul>
        ${items.map((item) => `<li>${String(item)}</li>`).join("")}
      </ul>
    </section>
  `;
}

export function renderAnalytics(container, research) {
  const kpis = research?.kpis || {};

  const cards = [
    { label: "Avg Views", value: kpis.avg_views ?? 0 },
    { label: "Max Views", value: kpis.max_views ?? 0 },
    { label: "Total Trends", value: kpis.total_trending_videos ?? 0 },
  ];

  container.innerHTML = `
    <div class="kpi-grid">
      ${cards
        .map(
          (item) => `
            <article class="kpi-card">
              <p class="kpi-label">${item.label}</p>
              <p class="kpi-value">${item.value}</p>
            </article>
          `
        )
        .join("")}
    </div>

    ${renderList("Top Keywords", (kpis.top_keywords || []).slice(0, 8))}
    ${renderList("Trending Titles", (research?.titles || []).slice(0, 6))}
    ${renderList("Top Video Examples", (kpis.top_video_examples || []).slice(0, 6))}
  `;
}
