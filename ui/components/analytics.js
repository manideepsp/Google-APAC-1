function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function formatNumber(value) {
  const num = Number(value || 0);
  if (!Number.isFinite(num)) {
    return "0";
  }
  return num.toLocaleString();
}

function sanitizeUrl(value) {
  const url = String(value || "").trim();
  if (!url) {
    return "";
  }
  if (url.startsWith("http://") || url.startsWith("https://")) {
    return url;
  }
  return "";
}

function inferVideoTypeAndCategory(title, channelInfo) {
  const text = `${title || ""} ${(channelInfo || "")}`.toLowerCase();

  const typeRules = [
    { type: "Trailer/Promo", words: ["trailer", "teaser", "official video", "promo"] },
    { type: "Music/Song", words: ["song", "lyrical", "music", "audio"] },
    { type: "Gaming", words: ["minecraft", "bgmi", "gameplay", "challenge", "gaming"] },
    { type: "Tutorial/Educational", words: ["how to", "tutorial", "explained", "guide"] },
    { type: "News/Update", words: ["news", "update", "report", "breaking"] },
    { type: "Vlog/Story", words: ["vlog", "day", "behind the scenes", "journey"] },
  ];

  const categoryRules = [
    { category: "Entertainment", words: ["trailer", "movie", "song", "music", "film"] },
    { category: "Gaming", words: ["minecraft", "bgmi", "game", "gaming", "challenge"] },
    { category: "Education", words: ["tutorial", "guide", "learn", "explained"] },
    { category: "Tech/AI", words: ["ai", "tech", "tool", "automation", "software"] },
    { category: "Lifestyle", words: ["vlog", "daily", "travel", "fitness", "food"] },
  ];

  const foundType = typeRules.find((rule) => rule.words.some((word) => text.includes(word)));
  const foundCategory = categoryRules.find((rule) => rule.words.some((word) => text.includes(word)));

  return {
    type: foundType ? foundType.type : "General Content",
    category: foundCategory ? foundCategory.category : "General",
  };
}

function tokenize(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .split(/\s+/)
    .filter((word) => word.length > 2);
}

function buildGoalRelationSummary({ goal, title, trendCategory, type, videoCategory, providedSummary }) {
  const summaryText = String(providedSummary || "").trim();
  const goalWords = tokenize(goal);
  const titleWords = new Set(tokenize(title));
  const matched = goalWords.filter((word) => titleWords.has(word)).slice(0, 3);

  if (summaryText) {
    if (matched.length) {
      return `${summaryText} Goal match: ${matched.join(", ")}.`;
    }
    return summaryText;
  }

  if (!goalWords.length) {
    return `Aligned to ${videoCategory || trendCategory || "general"} strategy.`;
  }

  if (matched.length) {
    return `Matches goal terms (${matched.join(", ")}) and fits ${type} in ${videoCategory}.`;
  }

  return `Supports ${videoCategory || trendCategory} direction for the active goal.`;
}

function flattenTopVideos(analyticsData) {
  const videos = [];
  for (const channelItem of analyticsData || []) {
    const channelData = channelItem?.data || {};
    const channelId = channelData.channel_id || channelItem?.channel_id || "";
    const channelTitle = channelData.channel_title || channelId || "Unknown Channel";
    const channelUrl = sanitizeUrl(channelData.channel_url) || (channelId ? `https://www.youtube.com/channel/${channelId}` : "");
    const channelInfo = `${channelTitle} ${channelItem?.channel_id || ""}`;

    for (const video of channelData.top_videos || []) {
      const videoId = video?.video_id || "";
      const videoUrl = sanitizeUrl(video?.video_url) || (videoId ? `https://www.youtube.com/watch?v=${videoId}` : "");
      const inferred = inferVideoTypeAndCategory(video?.title || "", channelInfo);
      videos.push({
        title: video?.title || "Untitled",
        views: Number(video?.views || 0),
        likes: Number(video?.likes || 0),
        channel: channelTitle,
        channelUrl,
        videoUrl,
        type: inferred.type,
        category: inferred.category,
      });
    }
  }

  return videos.sort((a, b) => b.views - a.views).slice(0, 12);
}

function buildAnalyticsRows(research) {
  const goal = research?.goal || "";
  const trendingTitles = (research?.titles || []).slice(0, 12);
  const topVideos = flattenTopVideos(research?.analytics || []);
  const rowCount = Math.max(trendingTitles.length, topVideos.length);

  if (!rowCount) {
    return [];
  }

  const rows = [];
  for (let idx = 0; idx < rowCount; idx += 1) {
    const video = topVideos[idx] || null;
    const trendTitle = trendingTitles[idx] || video?.title || "Untitled";
    const trendCategory = inferVideoTypeAndCategory(trendTitle, video?.channel || "").category;

    rows.push({
      title: video?.title || trendTitle,
      trendCategory,
      goalSummary: buildGoalRelationSummary({
        goal,
        title: trendTitle,
        trendCategory,
        type: video?.type || "General Content",
        videoCategory: video?.category || "General",
        providedSummary: "",
      }),
      channel: video?.channel || "Unknown Channel",
      channelUrl: video?.channelUrl || "",
      type: video?.type || "General Content",
      videoCategory: video?.category || "General",
      views: Number.isFinite(video?.views) ? video.views : null,
      likes: Number.isFinite(video?.likes) ? video.likes : null,
      videoUrl: video?.videoUrl || "",
    });
  }

  return rows;
}

function renderTopKeywords(keywords) {
  const items = (keywords || []).slice(0, 10);
  if (!items.length) {
    return "";
  }

  return `
    <section class="list-card">
      <h3 class="font-semibold">Top Keywords</h3>
      <p class="text-secondary text-sm mt-1">${items.map((word) => escapeHtml(word)).join(" | ")}</p>
    </section>
  `;
}

function renderAnalyticsTable(rows) {
  if (!rows.length) {
    return `
      <section class="list-card">
        <h3 class="font-semibold">Video Insights Table</h3>
        <div class="table-wrap">
          <table class="tasks-table insights-table">
            <thead>
              <tr>
                <th>Title</th>
                <th>Category</th>
                <th>Summary (Goal Relation)</th>
                <th>Channel</th>
                <th>Type</th>
                <th>Video Category</th>
                <th>Views</th>
                <th>Likes</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td colspan="8" class="text-secondary">No analytics rows available yet.</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    `;
  }

  return `
    <section class="list-card">
      <h3 class="font-semibold">Video Insights Table</h3>
      <div class="table-wrap">
        <table class="tasks-table insights-table">
          <thead>
            <tr>
              <th>Title</th>
              <th>Category</th>
              <th>Summary (Goal Relation)</th>
              <th>Channel</th>
              <th>Type</th>
              <th>Video Category</th>
              <th>Views</th>
              <th>Likes</th>
            </tr>
          </thead>
          <tbody>
            ${rows
              .map((row) => {
                const titleHtml = row.videoUrl
                  ? `<a class="table-link" href="${escapeHtml(row.videoUrl)}" target="_blank" rel="noreferrer noopener">${escapeHtml(row.title)}</a>`
                  : escapeHtml(row.title);

                const channelHtml = row.channelUrl
                  ? `<a class="table-link" href="${escapeHtml(row.channelUrl)}" target="_blank" rel="noreferrer noopener">${escapeHtml(row.channel)}</a>`
                  : escapeHtml(row.channel);

                const views = row.views === null ? "-" : formatNumber(row.views);
                const likes = row.likes === null ? "-" : formatNumber(row.likes);

                return `
                  <tr>
                    <td>${titleHtml}</td>
                    <td>${escapeHtml(row.trendCategory)}</td>
                    <td class="summary-cell" data-tooltip="${escapeHtml(row.goalSummary)}"><span class="summary-truncate">${escapeHtml(row.goalSummary)}</span></td>
                    <td>${channelHtml}</td>
                    <td>${escapeHtml(row.type)}</td>
                    <td>${escapeHtml(row.videoCategory)}</td>
                    <td>${views}</td>
                    <td>${likes}</td>
                  </tr>
                `;
              })
              .join("")}
          </tbody>
        </table>
      </div>
    </section>
  `;
}

export function renderAnalytics(container, research) {
  const kpis = research?.kpis || {};
  const rows = buildAnalyticsRows(research);

  const cards = [
    { label: "Avg Views", value: formatNumber(kpis.avg_views ?? 0) },
    { label: "Max Views", value: formatNumber(kpis.max_views ?? 0) },
    { label: "Total Trends", value: formatNumber(kpis.total_trending_videos ?? 0) },
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

    ${renderTopKeywords(kpis.top_keywords || [])}
    ${renderAnalyticsTable(rows)}
  `;
}
