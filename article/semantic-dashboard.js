(() => {
  const payload = window.semanticMap3D;
  if (!payload || !Array.isArray(payload.records)) return;

  const records = payload.records;
  const colors = payload.clusterColors || {};
  const clusters = Object.keys(colors).filter((cluster) => records.some((record) => record.cluster === cluster));
  const sources = Array.from(new Set(records.map((record) => record.source).filter(Boolean))).sort();
  const years = records.map((record) => Number(record.year)).filter(Number.isFinite);
  const yearMin = Math.min(...years);
  const yearMax = Math.max(...years);
  const sourcePalette = {
    DRA: "#26324C",
    "DLF/DLF Kultur": "#C25B72",
    Wirklichkeit: "#4747A1",
  };

  setHeroMetrics();
  renderSubjectSummary();
  renderCorpusTriage();
  renderClusterExplorer();
  renderSourceMix();
  renderFormMix();
  renderClusterProfiles();
  renderDecadeProfile();
  renderDurationScale();

  window.requestAnimationFrame(() => {
    document.querySelectorAll("[data-fill]").forEach((el) => {
      el.style.width = el.dataset.fill;
    });
    document.querySelectorAll("[data-height]").forEach((el) => {
      el.style.height = el.dataset.height;
    });
  });

  function setHeroMetrics() {
    const values = [
      [records.length, "curated map entries"],
      [clusters.length, "semantic clusters"],
      [sources.length, "source collections"],
      [yearMax - yearMin + 1, "years covered"],
    ];
    document.querySelectorAll(".hero-metrics div").forEach((item, index) => {
      const strong = item.querySelector("strong");
      const span = item.querySelector("span");
      if (!strong || !span || !values[index]) return;
      strong.dataset.count = String(values[index][0]);
      span.textContent = values[index][1];
    });
  }

  function renderSubjectSummary() {
    const host = document.querySelector("[data-subject-summary]");
    if (!host) return;
    const top = countMany(records.flatMap((record) => record.whoAbout || []))
      .filter(([label]) => label && label !== "not stated")
      .slice(0, 8);
    host.innerHTML = top.map(([label, count]) => `<span><b>${count}</b>${escapeHtml(label)}</span>`).join("");
  }

  function renderCorpusTriage() {
    const host = document.querySelector("[data-corpus-triage]");
    if (!host) return;
    const sourceCounts = countBy(records, (record) => record.source || "Unknown");
    const clusterCounts = countBy(records, (record) => record.cluster || "Unknown");
    const maxSource = sourceCounts[0]?.[1] || 1;
    const sourceRows = sourceCounts.map(([source, count], index) => `
      <div class="source-ribbon">
        <strong title="${escapeHtml(source)}">${escapeHtml(source)}</strong>
        <span class="source-line"><i data-fill="${((count / maxSource) * 100).toFixed(2)}%" style="background:${sourcePalette[source] || pickColor(index)}"></i></span>
        <span>${count}</span>
      </div>
    `).join("");
    const clusterTiles = clusterCounts.map(([cluster, count], index) => `
      <article class="cluster-tile" title="${escapeHtml(cluster)}: ${count} records">
        <i style="background:${colors[cluster] || pickColor(index)}"></i>
        <strong>${escapeHtml(cluster)}</strong>
        <b>${count}</b>
        <span>${((count / records.length) * 100).toFixed(1)}% of map</span>
      </article>
    `).join("");
    host.innerHTML = `
      <div class="triage-panel">
        <div class="triage-top">
          <div>
            <div class="triage-number">${records.length}</div>
            <p class="triage-caption">curated entries in the semantic map after removing the non-life-writing item.</p>
          </div>
          <div>
            <span class="panel-kicker">Source collections</span>
            <h3 class="panel-title">Where the curated map records come from</h3>
            <div class="triage-source">${sourceRows}</div>
          </div>
        </div>
        <span class="panel-kicker">Semantic clusters</span>
        <div class="cluster-tiles">${clusterTiles}</div>
      </div>
      <div class="stat-cards">
        <div class="stat-card"><b>${records.length}</b><span>map records</span></div>
        <div class="stat-card"><b>${yearMin}-${yearMax}</b><span>broadcast years</span></div>
        <div class="stat-card"><b>${clusters.length}</b><span>active clusters</span></div>
      </div>
    `;
  }

  function renderClusterExplorer() {
    const host = document.querySelector("[data-cluster-explorer]");
    if (!host) return;
    const stats = clusters.map((cluster) => clusterStats(cluster)).sort((a, b) => b.records.length - a.records.length);
    let active = stats[0]?.cluster || "";
    host.innerHTML = `
      <div class="cluster-layout">
        <div class="cluster-list" data-cluster-list></div>
        <div class="cluster-detail panel-pad" data-cluster-detail></div>
      </div>
    `;
    const list = host.querySelector("[data-cluster-list]");
    const detail = host.querySelector("[data-cluster-detail]");

    function draw() {
      list.innerHTML = stats.map((stat) => `
        <button class="cluster-button" type="button" data-cluster="${escapeHtml(stat.cluster)}" aria-pressed="${stat.cluster === active}">
          <i style="background:${colors[stat.cluster] || "#8693AC"}"></i>
          <strong>${escapeHtml(stat.cluster)}</strong>
          <b>${stat.records.length}</b>
        </button>
      `).join("");
      const stat = stats.find((item) => item.cluster === active) || stats[0];
      const sourceText = stat.sources.map(([source, count]) => `${source} ${count}`).join(" / ");
      const focuses = stat.focuses.slice(0, 5).map(([label, count], index) => barRow({
        label,
        count,
        max: stat.focuses[0]?.[1] || 1,
        color: colors[stat.cluster] || pickColor(index),
        delay: index,
      })).join("");
      const exemplars = stat.records.slice(0, 4).map((record) => exemplarCard(record)).join("");
      detail.innerHTML = `
        <div class="panel-head">
          <div>
            <span class="panel-kicker">Selected cluster</span>
            <h3 class="panel-title">${escapeHtml(stat.cluster)}</h3>
            <p class="panel-note">${escapeHtml(sourceText || "No source split available")}</p>
          </div>
        </div>
        <div class="detail-metrics">
          <span><b>${stat.records.length}</b>records</span>
          <span><b>${stat.yearMin}-${stat.yearMax}</b>years</span>
          <span><b>${stat.forms.length}</b>genres</span>
        </div>
        <div class="bar-stack">${focuses || `<div class="empty-state">No life-focus tags in this cluster.</div>`}</div>
        <div class="exemplar-grid" style="margin-top:16px">${exemplars}</div>
      `;
      window.requestAnimationFrame(() => detail.querySelectorAll("[data-fill]").forEach((el) => {
        el.style.width = el.dataset.fill;
      }));
    }

    list.addEventListener("click", (event) => {
      const button = event.target.closest("[data-cluster]");
      if (!button) return;
      active = button.dataset.cluster;
      draw();
    });
    detail.addEventListener("click", (event) => {
      const card = event.target.closest("[data-open-window]");
      if (!card) return;
      event.preventDefault();
      event.stopPropagation();
      const url = card.dataset.openWindow;
      const opened = window.open(url, "radioLifeSourceWindow", "popup=yes,width=1180,height=860,left=80,top=60,noopener,noreferrer");
      if (opened) opened.opener = null;
    });
    draw();
  }

  function renderSourceMix() {
    const host = document.querySelector("[data-source-mix]");
    if (!host) return;
    const rows = clusters.map((cluster) => {
      const subset = records.filter((record) => record.cluster === cluster);
      const counts = new Map(countBy(subset, (record) => record.source || "Unknown"));
      const segments = sources.map((source) => {
        const count = counts.get(source) || 0;
        const width = subset.length ? (count / subset.length) * 100 : 0;
        return `<span class="stack-segment" data-fill="${width.toFixed(2)}%" style="background:${sourcePalette[source] || "#8693AC"}" title="${escapeHtml(source)}: ${count}"></span>`;
      }).join("");
      return `
        <div class="bar-row">
          <span class="bar-label">${escapeHtml(cluster)}</span>
          <span class="bar-track">${segments}</span>
          <span class="bar-value">${subset.length}</span>
        </div>
      `;
    }).join("");
    host.innerHTML = `
      <div class="panel-pad">
        <div class="panel-head">
          <div>
            <span class="panel-kicker">Stacked by source</span>
            <h3 class="panel-title">Each row sums to one cluster</h3>
          </div>
          <div class="chip-row">${sources.map((source) => `<span><i class="source-dot" style="background:${sourcePalette[source] || "#8693AC"}"></i>${escapeHtml(source)}</span>`).join("")}</div>
        </div>
        <div class="bar-stack">${rows}</div>
      </div>
    `;
  }

  function renderFormMix() {
    const host = document.querySelector("[data-form-mix]");
    if (!host) return;
    const families = countBy(records, (record) => formFamily(record.form || record.genre || ""));
    const max = families[0]?.[1] || 1;
    host.innerHTML = `
      <div class="panel-pad">
        <div class="panel-head">
          <div>
            <span class="panel-kicker">Form families</span>
            <h3 class="panel-title">Grouped from map genres</h3>
          </div>
        </div>
        <div class="bar-stack">
          ${families.map(([label, count], index) => barRow({ label, count, max, color: pickColor(index), delay: index })).join("")}
        </div>
      </div>
    `;
  }

  function renderClusterProfiles() {
    const host = document.querySelector("[data-cluster-profiles]");
    if (!host) return;
    const tags = countMany(records.flatMap((record) => record.whoAbout || []))
      .filter(([label]) => label && label !== "not stated")
      .slice(0, 6)
      .map(([label]) => label);
    const rows = clusters.map((cluster) => {
      const subset = records.filter((record) => record.cluster === cluster);
      const counts = new Map(countMany(subset.flatMap((record) => record.whoAbout || [])));
      const max = Math.max(...tags.map((tag) => counts.get(tag) || 0), 1);
      const cells = tags.map((tag) => {
        const value = counts.get(tag) || 0;
        const width = `${((value / max) * 100).toFixed(2)}%`;
        return `<span class="profile-cell" style="color:${colors[cluster] || "#8693AC"}" title="${escapeHtml(tag)}: ${value} in ${escapeHtml(cluster)}"><i data-fill="${width}"></i><span>${value || ""}</span></span>`;
      }).join("");
      return `<div class="profile-row"><strong title="${escapeHtml(cluster)}">${escapeHtml(cluster)}</strong>${cells}</div>`;
    }).join("");
    host.innerHTML = `
      <div class="panel-pad" style="--cols:${tags.length}">
        <div class="panel-head">
          <div>
            <span class="panel-kicker">Life-focus matrix</span>
            <h3 class="panel-title">Counts in the top shared life-focus tags</h3>
          </div>
        </div>
        <div class="profile-grid">
          <div class="profile-head"><span></span>${tags.map((tag) => `<span>${escapeHtml(tag)}</span>`).join("")}</div>
          ${rows}
        </div>
      </div>
    `;
  }

  function renderDurationScale() {
    const host = document.querySelector("[data-duration-scale]");
    const durationPayload = window.durationScaleData;
    if (!host || !durationPayload || !Array.isArray(durationPayload.records)) return;
    const durationRecords = durationPayload.records.filter((record) => Number.isFinite(Number(record.duration)));
    if (!durationRecords.length) {
      host.innerHTML = `<div class="empty-state">No duration metadata available for the current semantic map.</div>`;
      return;
    }
    let active = new Set(clusters.filter((cluster) => durationRecords.some((record) => record.cluster === cluster)));
    const maxDuration = Math.ceil(Math.min(160, Math.max(...durationRecords.map((record) => Number(record.duration)))) / 20) * 20;
    host.innerHTML = `
      <div class="duration-viz">
        <div class="duration-controls">
          <div>
            <span class="panel-kicker">Matched duration metadata</span>
            <h3 class="panel-title">${durationRecords.length} of ${durationPayload.mapRecords || records.length} map records</h3>
          </div>
          <div class="chip-row" data-duration-clusters></div>
        </div>
        <div class="duration-chart" data-duration-chart></div>
        <div class="duration-foot">
          <span>Dots beyond ${maxDuration} minutes are clipped to the right edge.</span>
          <span>Box = Q1-Q3; line = median; whisker = 10th-90th percentile.</span>
        </div>
      </div>
    `;
    const clusterHost = host.querySelector("[data-duration-clusters]");
    const chart = host.querySelector("[data-duration-chart]");
    const tooltip = document.createElement("div");
    tooltip.className = "duration-tooltip";
    tooltip.hidden = true;
    chart.appendChild(tooltip);

    clusterHost.innerHTML = clusters.filter((cluster) => durationRecords.some((record) => record.cluster === cluster)).map((cluster) => `
      <button type="button" data-duration-cluster="${escapeHtml(cluster)}" aria-pressed="true">
        <i style="background:${colors[cluster] || "#8693AC"}"></i>${escapeHtml(cluster)}
      </button>
    `).join("");

    function draw() {
      const activeClusters = clusters.filter((cluster) => active.has(cluster) && durationRecords.some((record) => record.cluster === cluster));
      const ticks = Array.from({ length: 9 }, (_, index) => index * (maxDuration / 8));
      const rows = activeClusters.map((cluster, rowIndex) => {
        const subset = durationRecords.filter((record) => record.cluster === cluster).sort((a, b) => Number(a.duration) - Number(b.duration));
        const durations = subset.map((record) => Number(record.duration));
        const q10 = quantile(durations, 0.1);
        const q1 = quantile(durations, 0.25);
        const med = quantile(durations, 0.5);
        const q3 = quantile(durations, 0.75);
        const q90 = quantile(durations, 0.9);
        const points = subset.map((record, index) => {
          const left = scaleDuration(Number(record.duration), maxDuration);
          const jitter = deterministicJitter(`${record.title}-${record.year}-${index}`) * 34;
          return `<span class="duration-point" data-duration-point style="left:${left}%;margin-top:${jitter}px;background:${colors[cluster] || "#8693AC"}" data-title="${escapeAttr(record.title)}" data-meta="${escapeAttr([record.duration + ' min', record.year, record.source].filter(Boolean).join(' · '))}"></span>`;
        }).join("");
        return `
          <div class="duration-row">
            <span class="duration-label">${escapeHtml(cluster)}</span>
            <span class="duration-whisker" style="left:${scaleDuration(q10, maxDuration)}%;width:${Math.max(0, scaleDuration(q90, maxDuration) - scaleDuration(q10, maxDuration)).toFixed(2)}%"></span>
            <span class="duration-box" style="left:${scaleDuration(q1, maxDuration)}%;width:${Math.max(0.8, scaleDuration(q3, maxDuration) - scaleDuration(q1, maxDuration)).toFixed(2)}%"></span>
            <span class="duration-median" style="left:${scaleDuration(med, maxDuration)}%"></span>
            ${points}
          </div>
        `;
      }).join("");
      chart.innerHTML = `
        <div class="duration-grid">${ticks.slice(0, -1).map(() => "<i></i>").join("")}</div>
        ${rows || `<div class="empty-state">Select at least one cluster.</div>`}
        <div class="duration-axis">${ticks.map((tick) => `<span>${Math.round(tick)}</span>`).join("")}</div>
      `;
      chart.appendChild(tooltip);
    }

    clusterHost.addEventListener("click", (event) => {
      const button = event.target.closest("[data-duration-cluster]");
      if (!button) return;
      const cluster = button.dataset.durationCluster;
      if (active.has(cluster)) active.delete(cluster);
      else active.add(cluster);
      button.setAttribute("aria-pressed", String(active.has(cluster)));
      draw();
    });

    chart.addEventListener("pointermove", (event) => {
      const point = event.target.closest("[data-duration-point]");
      if (!point) {
        tooltip.hidden = true;
        return;
      }
      const rect = chart.getBoundingClientRect();
      tooltip.hidden = false;
      tooltip.innerHTML = `<strong>${escapeHtml(point.dataset.title)}</strong>${escapeHtml(point.dataset.meta)}`;
      tooltip.style.left = `${Math.min(rect.width - 274, event.clientX - rect.left + 12)}px`;
      tooltip.style.top = `${Math.max(8, event.clientY - rect.top - 18)}px`;
    });
    chart.addEventListener("pointerleave", () => {
      tooltip.hidden = true;
    });
    draw();
  }

  function renderDecadeProfile() {
    const host = document.querySelector("[data-decade-profile]");
    if (!host) return;
    const decades = Array.from(new Set(records.map((record) => decade(record.year)).filter(Boolean))).sort((a, b) => a - b);
    const max = Math.max(...clusters.flatMap((cluster) => {
      const subset = records.filter((record) => record.cluster === cluster);
      const counts = new Map(countBy(subset, (record) => decade(record.year)));
      return decades.map((item) => counts.get(item) || 0);
    }), 1);
    const rows = clusters.map((cluster) => {
      const subset = records.filter((record) => record.cluster === cluster);
      const counts = new Map(countBy(subset, (record) => decade(record.year)));
      const cols = decades.map((item) => {
        const value = counts.get(item) || 0;
        const height = `${Math.max(3, (value / max) * 100).toFixed(1)}%`;
        return `<span class="timeline-col" data-height="${height}" style="background:${colors[cluster] || "#8693AC"}" title="${item}s: ${value}"></span>`;
      }).join("");
      return `<div class="timeline-row"><span class="bar-label">${escapeHtml(cluster)}</span><div class="timeline-track">${cols}</div></div>`;
    }).join("");
    host.innerHTML = `
      <div class="panel-pad">
        <div class="panel-head">
          <div>
            <span class="panel-kicker">Decades</span>
            <h3 class="panel-title">${decades[0]}s to ${decades[decades.length - 1]}s</h3>
          </div>
        </div>
        <div class="timeline-bars">${rows}</div>
      </div>
    `;
  }

  function clusterStats(cluster) {
    const subset = records.filter((record) => record.cluster === cluster);
    const clusterYears = subset.map((record) => Number(record.year)).filter(Number.isFinite);
    return {
      cluster,
      records: subset,
      yearMin: Math.min(...clusterYears),
      yearMax: Math.max(...clusterYears),
      sources: countBy(subset, (record) => record.source || "Unknown"),
      focuses: countMany(subset.flatMap((record) => record.whoAbout || [])).filter(([label]) => label && label !== "not stated"),
      forms: countBy(subset, (record) => record.form || record.genre || "Unknown"),
    };
  }

  function exemplarCard(record) {
    const meta = [record.year, record.source, record.form || record.genre].filter(Boolean).join(" · ");
    const description = record.description || record.subjectDescription || "No short description available.";
    const url = String(record.url || "").trim();
    const tag = /^https?:\/\//i.test(url) ? "button" : "article";
    const linkAttrs = tag === "button" ? ` type="button" data-open-window="${escapeAttr(url)}" aria-label="Open ${escapeAttr(record.title)} source in a new window"` : "";
    return `
      <${tag} class="exemplar-card"${linkAttrs}>
        <strong>${escapeHtml(record.title)}</strong>
        <span>${escapeHtml(meta)}</span>
        <span>${escapeHtml(record.protagonist || "No protagonist listed")}</span>
        <p>${escapeHtml(description)}</p>
      </${tag}>
    `;
  }

  function barRow({ label, count, max, color, delay }) {
    const width = max ? `${Math.max(1.2, (count / max) * 100).toFixed(2)}%` : "0%";
    return `
      <div class="bar-row">
        <span class="bar-label" title="${escapeHtml(label)}">${escapeHtml(label)}</span>
        <span class="bar-track"><span class="bar-fill" data-fill="${width}" style="background:${color};transition-delay:${(delay * 0.04).toFixed(2)}s"></span></span>
        <span class="bar-value">${count}</span>
      </div>
    `;
  }

  function countBy(items, getter) {
    const counts = new Map();
    items.forEach((item) => {
      const key = getter(item);
      if (!key) return;
      counts.set(key, (counts.get(key) || 0) + 1);
    });
    return Array.from(counts.entries()).sort((a, b) => b[1] - a[1] || String(a[0]).localeCompare(String(b[0])));
  }

  function countMany(values) {
    return countBy(values, (value) => value);
  }

  function formFamily(value) {
    const text = String(value || "").toLowerCase();
    if (text.includes("feature") || text.includes("freistil") || text.includes("doku")) return "Feature / documentary";
    if (text.includes("bearbeitung") || text.includes("lesung")) return "Adaptation / reading";
    if (text.includes("portrait") || text.includes("porträt")) return "Portrait";
    if (text.includes("ars acustica") || text.includes("sound") || text.includes("hörstück")) return "Sound art";
    if (text.includes("original")) return "Original radio play";
    if (text.includes("gespräch") || text.includes("essay") || text.includes("kommentar")) return "Talk / essay";
    return "Other / mixed";
  }

  function decade(year) {
    const value = Number(year);
    if (!Number.isFinite(value)) return "";
    return Math.floor(value / 10) * 10;
  }

  function pickColor(index) {
    return ["#26324C", "#C25B72", "#4747A1", "#5D9BB5", "#C29A45", "#D07A56", "#6F8FC9"][index % 7];
  }

  function quantile(values, p) {
    if (!values.length) return 0;
    const pos = (values.length - 1) * p;
    const base = Math.floor(pos);
    const rest = pos - base;
    return values[base + 1] === undefined ? values[base] : values[base] + rest * (values[base + 1] - values[base]);
  }

  function scaleDuration(value, max) {
    return Math.max(0, Math.min(100, (Number(value) / max) * 100));
  }

  function deterministicJitter(text) {
    let hash = 0;
    String(text).split("").forEach((char) => {
      hash = (hash * 31 + char.charCodeAt(0)) | 0;
    });
    return ((Math.abs(hash) % 1000) / 1000 - 0.5);
  }

  function escapeAttr(value) {
    return escapeHtml(value).replace(/`/g, "&#096;");
  }

  function hexToRgba(hex, alpha) {
    const clean = String(hex).replace("#", "");
    const full = clean.length === 3 ? clean.split("").map((char) => char + char).join("") : clean;
    const num = Number.parseInt(full, 16);
    const r = (num >> 16) & 255;
    const g = (num >> 8) & 255;
    const b = num & 255;
    return `rgba(${r},${g},${b},${Math.max(0, Math.min(1, alpha)).toFixed(3)})`;
  }

  function escapeHtml(value) {
    return String(value || "").replace(/[&<>"']/g, (char) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#039;",
    }[char]));
  }
})();
