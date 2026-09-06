(() => {
  "use strict";

  const state = {
    meta: null,
    incidents: [],
    activeIncidentId: null,
    chart: null,
    currentAuthor: localStorage.getItem("incidentDeskAuthor") || "",
  };

  const TYPE_COLORS = [
    "#2F5D50",
    "#3B6EA5",
    "#7D5BA6",
    "#C08A2E",
    "#C1622D",
    "#3F8F6F",
    "#8B948C",
    "#A33B3B",
    "#5C665F",
  ];

  const el = (sel, root = document) => root.querySelector(sel);
  const els = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  // ------------------------------------------------------------------
  // API
  // ------------------------------------------------------------------
  async function api(path, options = {}) {
    const res = await fetch(path, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
    let body = null;
    try {
      body = await res.json();
    } catch {
      /* no body */
    }
    if (!res.ok) {
      const error = new Error((body && body.error) || "Request failed.");
      error.status = res.status;
      error.errors = body && body.errors;
      throw error;
    }
    return body;
  }

  // ------------------------------------------------------------------
  // Toasts
  // ------------------------------------------------------------------
  function toast(message, isError = false) {
    const container = el("#toast-container");
    const node = document.createElement("div");
    node.className = "toast" + (isError ? " is-error" : "");
    node.textContent = message;
    container.appendChild(node);
    setTimeout(() => node.remove(), 3600);
  }

  // ------------------------------------------------------------------
  // View routing
  // ------------------------------------------------------------------
  function goToView(name) {
    els(".view").forEach((v) => v.classList.remove("is-active"));
    els(".rail-link").forEach((b) => b.classList.remove("is-active"));
    el(`#view-${name}`).classList.add("is-active");
    els(`.rail-link[data-view="${name}"]`).forEach((b) =>
      b.classList.add("is-active"),
    );
    if (name === "dashboard") loadIncidents();
    if (name === "trends") loadTrends();
  }

  els(".rail-link").forEach((btn) => {
    btn.addEventListener("click", () => goToView(btn.dataset.view));
  });

  // ------------------------------------------------------------------
  // Current author — set once, used for every audit-logged action
  // (status/severity changes, reopen) instead of a prompt() per action.
  // ------------------------------------------------------------------
  const authorInput = el("#current-author");
  authorInput.value = state.currentAuthor;
  authorInput.addEventListener("input", () => {
    state.currentAuthor = authorInput.value;
    localStorage.setItem("incidentDeskAuthor", authorInput.value);
    if (authorInput.value.trim()) {
      authorInput.classList.remove("input-error");
      el("#current-author-error").textContent = "";
    }
  });

  function requireCurrentAuthor() {
    const author = state.currentAuthor.trim();
    if (!author) {
      authorInput.classList.add("input-error");
      el("#current-author-error").textContent =
        "Set your name before making changes.";
      authorInput.focus();
      toast("Set \u201cActing as\u201d before making changes.", true);
      return null;
    }
    return author;
  }

  // ------------------------------------------------------------------
  // Meta (vocab) — populate all selects from the server's source of truth
  // ------------------------------------------------------------------
  async function loadMeta() {
    state.meta = await api("/api/meta");

    fillSelect(el("#filter-status"), state.meta.statuses, "All", true);
    fillSelect(el("#filter-severity"), state.meta.severities, "All", true);
    fillSelect(
      el("#f-type"),
      state.meta.incident_types,
      "Select a type…",
      false,
    );
    fillSelect(
      el("#f-severity"),
      state.meta.severities,
      "Select severity…",
      false,
    );
  }

  function fillSelect(selectEl, options, placeholder, keepFirstBlank) {
    const existingFirst = keepFirstBlank ? selectEl.firstElementChild : null;
    selectEl.innerHTML = "";
    if (keepFirstBlank) {
      const opt = document.createElement("option");
      opt.value = "";
      opt.textContent = placeholder;
      selectEl.appendChild(opt);
    } else {
      const opt = document.createElement("option");
      opt.value = "";
      opt.textContent = placeholder;
      opt.disabled = true;
      opt.selected = true;
      selectEl.appendChild(opt);
    }
    options.forEach((value) => {
      const opt = document.createElement("option");
      opt.value = value;
      opt.textContent = value;
      selectEl.appendChild(opt);
    });
  }

  // ------------------------------------------------------------------
  // Dashboard: incident list
  // ------------------------------------------------------------------
  function slugify(value) {
    return value.toLowerCase().replace(/[^a-z]+/g, "-");
  }

  function formatDateTime(iso) {
    if (!iso) return "—";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  }

  async function loadIncidents() {
    const status = el("#filter-status").value;
    const severity = el("#filter-severity").value;
    const sort = el("#filter-sort").value;
    const params = new URLSearchParams();
    if (status) params.set("status", status);
    if (severity) params.set("severity", severity);
    if (sort) params.set("sort", sort);

    const incidents = await api(`/api/incidents?${params.toString()}`);
    state.incidents = incidents;
    renderIncidentRows(incidents);
  }

  function renderIncidentRows(incidents) {
    const tbody = el("#incident-rows");
    tbody.innerHTML = "";
    el("#empty-state").classList.toggle("hidden", incidents.length > 0);
    el("#incident-count-label").textContent =
      incidents.length === 1 ? "1 incident" : `${incidents.length} incidents`;

    incidents.forEach((inc) => {
      const tr = document.createElement("tr");
      tr.className = `row-sev-${slugify(inc.severity)}`;
      tr.innerHTML = `
        <td class="cell-id">#${String(inc.id).padStart(4, "0")}</td>
        <td>${escapeHtml(inc.incident_type)}</td>
        <td><span class="chip chip-sev-${slugify(inc.severity)}">${inc.severity}</span></td>
        <td><span class="chip chip-status-${slugify(inc.status)}">${inc.status}</span></td>
        <td>${escapeHtml(inc.reporter)}</td>
        <td class="cell-discovered">${formatDateTime(inc.discovery_time)}</td>
        <td class="cell-updates">${inc.timeline_count}</td>
      `;
      tr.addEventListener("click", () => openDrawer(inc.id));
      tbody.appendChild(tr);
    });
  }

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str ?? "";
    return div.innerHTML;
  }

  ["#filter-status", "#filter-severity", "#filter-sort"].forEach((sel) => {
    el(sel).addEventListener("change", loadIncidents);
  });

  // ------------------------------------------------------------------
  // New incident form
  // ------------------------------------------------------------------
  const form = el("#incident-form");
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    els(".field-error").forEach((p) => (p.textContent = ""));
    const statusEl = el("#form-status");
    statusEl.textContent = "";
    statusEl.className = "form-status";

    const discoveryRaw = el("#f-discovery").value; // "YYYY-MM-DDTHH:MM"
    const payload = {
      incident_type: el("#f-type").value,
      discovery_time: discoveryRaw,
      initial_severity: el("#f-severity").value,
      reporter: el("#f-reporter").value,
      description: el("#f-description").value,
    };

    const submitBtn = form.querySelector('button[type="submit"]');
    submitBtn.disabled = true;
    try {
      const created = await api("/api/incidents", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      statusEl.textContent = `Filed as incident #${String(created.id).padStart(4, "0")}.`;
      statusEl.classList.add("is-success");
      form.reset();
      toast(`Incident #${String(created.id).padStart(4, "0")} filed.`);
    } catch (err) {
      if (err.errors) {
        Object.entries(err.errors).forEach(([field, message]) => {
          const p = el(`.field-error[data-for="${field}"]`);
          if (p) p.textContent = message;
        });
        statusEl.textContent = "Fix the highlighted fields.";
      } else {
        statusEl.textContent = err.message;
      }
      statusEl.classList.add("is-error");
    } finally {
      submitBtn.disabled = false;
    }
  });

  // ------------------------------------------------------------------
  // Drawer: incident detail
  // ------------------------------------------------------------------
  const drawer = el("#drawer");
  const drawerBackdrop = el("#drawer-backdrop");

  function closeDrawer() {
    drawer.classList.remove("is-open");
    drawerBackdrop.classList.add("hidden");
    state.activeIncidentId = null;
  }
  el("#drawer-close").addEventListener("click", closeDrawer);
  drawerBackdrop.addEventListener("click", closeDrawer);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeDrawer();
  });

  async function openDrawer(id) {
    state.activeIncidentId = id;
    const incident = await api(`/api/incidents/${id}`);
    renderDrawer(incident);
    drawer.classList.add("is-open");
    drawerBackdrop.classList.remove("hidden");
  }

  function renderDrawer(incident) {
    el("#drawer-id").textContent = `#${String(incident.id).padStart(4, "0")}`;
    el("#drawer-type").textContent = incident.incident_type;

    const isClosed = incident.status === "Closed";
    const body = el("#drawer-body");

    const statusOptions = state.meta.statuses
      .map(
        (s) =>
          `<option value="${s}" ${s === incident.status ? "selected" : ""}>${s}</option>`,
      )
      .join("");
    const severityOptions = state.meta.severities
      .map(
        (s) =>
          `<option value="${s}" ${s === incident.severity ? "selected" : ""}>${s}</option>`,
      )
      .join("");

    const timelineHtml =
      incident.timeline
        .map(
          (t) => `
      <div class="timeline-entry">
        <div class="timeline-time">${formatDateTime(t.timestamp)}</div>
        <div class="timeline-content ${t.entry_type !== "note" ? "is-system" : ""}">
          <div class="timeline-author">${escapeHtml(t.author)}</div>
          <div class="timeline-note">${escapeHtml(t.note)}</div>
        </div>
      </div>
    `,
        )
        .join("") || `<p class="detail-value">No updates logged yet.</p>`;

    body.innerHTML = `
      ${
        isClosed
          ? `
        <div class="closed-banner">
          <span>This incident is closed. Reopen it to make changes.</span>
          <form id="reopen-form" class="reopen-form">
            <input type="text" id="reopen-reason" placeholder="Reason for reopening (optional)">
            <button type="submit" class="btn btn-secondary">Reopen</button>
          </form>
        </div>
      `
          : ""
      }

      <div class="detail-grid">
        <div class="detail-field">
          <span class="detail-label">Reporter</span>
          <span class="detail-value">${escapeHtml(incident.reporter)}</span>
        </div>
        <div class="detail-field">
          <span class="detail-label">Discovered</span>
          <span class="detail-value mono">${formatDateTime(incident.discovery_time)}</span>
        </div>
        <div class="detail-field">
          <span class="detail-label">Filed</span>
          <span class="detail-value mono">${formatDateTime(incident.created_at)}</span>
        </div>
        <div class="detail-field">
          <span class="detail-label">Initial severity</span>
          <span class="detail-value">${incident.initial_severity}</span>
        </div>
      </div>

      <div>
        <div class="section-title">Description</div>
        <div class="description-block">${escapeHtml(incident.description)}</div>
      </div>

      <div>
        <div class="section-title">Status &amp; severity</div>
        <div class="control-row">
          <label>Status
            <select id="ctl-status" ${isClosed ? "disabled" : ""}>${statusOptions}</select>
          </label>
          <label>Severity
            <select id="ctl-severity" ${isClosed ? "disabled" : ""}>${severityOptions}</select>
          </label>
        </div>
      </div>

      <div>
        <div class="section-title">Timeline</div>
        <div class="timeline-list">${timelineHtml}</div>
        ${
          !isClosed
            ? `
          <form class="timeline-form" id="timeline-form" style="margin-top:14px;">
            <textarea id="tl-note" rows="3" placeholder="Add an update: what was found, done, or decided." required></textarea>
            <button type="submit" class="btn btn-secondary" style="align-self:flex-start;">Add update</button>
          </form>
        `
            : ""
        }
      </div>

      <div>
        <div class="section-title">Post-incident report</div>
        <button class="btn btn-secondary" id="btn-load-report">
          ${incident.report ? "Open report" : "Generate report draft"}
        </button>
        <div id="report-panel"></div>
      </div>
    `;

    if (!isClosed) {
      el("#ctl-status").addEventListener("change", (e) =>
        patchIncident({ status: e.target.value }),
      );
      el("#ctl-severity").addEventListener("change", (e) =>
        patchIncident({ severity: e.target.value }),
      );
      el("#timeline-form").addEventListener("submit", submitTimelineEntry);
    } else {
      el("#reopen-form").addEventListener("submit", reopenIncident);
    }
    el("#btn-load-report").addEventListener("click", () =>
      loadReportPanel(incident.id),
    );
  }

  async function patchIncident(patch) {
    const author = requireCurrentAuthor();
    if (!author) {
      openDrawer(state.activeIncidentId);
      return;
    }
    try {
      await api(`/api/incidents/${state.activeIncidentId}`, {
        method: "PATCH",
        body: JSON.stringify({ ...patch, author }),
      });
      toast("Incident updated.");
      await openDrawer(state.activeIncidentId);
      loadIncidents();
    } catch (err) {
      toast(err.message, true);
      openDrawer(state.activeIncidentId);
    }
  }

  async function reopenIncident(e) {
    e.preventDefault();
    const author = requireCurrentAuthor();
    if (!author) return;
    const reason = el("#reopen-reason").value.trim();
    try {
      await api(`/api/incidents/${state.activeIncidentId}/reopen`, {
        method: "POST",
        body: JSON.stringify({ author, reason }),
      });
      toast("Incident reopened.");
      await openDrawer(state.activeIncidentId);
      loadIncidents();
    } catch (err) {
      toast(err.message, true);
    }
  }

  async function submitTimelineEntry(e) {
    e.preventDefault();
    const author = requireCurrentAuthor();
    if (!author) return;
    const note = el("#tl-note").value.trim();
    if (!note) return;
    try {
      await api(`/api/incidents/${state.activeIncidentId}/timeline`, {
        method: "POST",
        body: JSON.stringify({ author, note }),
      });
      await openDrawer(state.activeIncidentId);
      loadIncidents();
    } catch (err) {
      toast(err.message, true);
    }
  }

  // ------------------------------------------------------------------
  // Report auto-fill panel
  // ------------------------------------------------------------------
  async function loadReportPanel(incidentId) {
    const data = await api(`/api/incidents/${incidentId}/report`);
    const panel = el("#report-panel");
    const inc = data.incident;
    const timelineSummary =
      data.timeline
        .map((t) => `- [${formatDateTime(t.timestamp)}] ${t.author}: ${t.note}`)
        .join("\n") || "No timeline entries recorded.";

    panel.innerHTML = `
      <div class="description-block" style="margin-top:12px; font-family: var(--font-mono); font-size: 12px; white-space: pre-wrap;">
Type: ${inc.incident_type}
Discovered: ${formatDateTime(inc.discovery_time)}
Initial severity: ${inc.initial_severity} → Current: ${inc.severity}
Status: ${inc.status}
Reporter: ${inc.reporter}

Timeline:
${timelineSummary}
      </div>
      <div class="report-fields" style="margin-top:16px;">
        <div class="report-field">
          <label for="rp-root-cause">Root cause</label>
          <textarea id="rp-root-cause" rows="3" placeholder="What ultimately caused this incident?">${escapeHtml(data.report.root_cause)}</textarea>
        </div>
        <div class="report-field">
          <label for="rp-remediation">Remediation</label>
          <textarea id="rp-remediation" rows="3" placeholder="What was done to fix it and prevent recurrence?">${escapeHtml(data.report.remediation)}</textarea>
        </div>
        <div class="report-field">
          <label for="rp-lessons">Lessons learned</label>
          <textarea id="rp-lessons" rows="3" placeholder="What should change going forward?">${escapeHtml(data.report.lessons_learned)}</textarea>
        </div>
        <div>
          <button class="btn btn-primary" id="btn-save-report">Save report</button>
          <span id="report-save-status" class="form-status"></span>
        </div>
      </div>
    `;

    el("#btn-save-report").addEventListener("click", async () => {
      const statusEl = el("#report-save-status");
      try {
        await api(`/api/incidents/${incidentId}/report`, {
          method: "PUT",
          body: JSON.stringify({
            root_cause: el("#rp-root-cause").value,
            remediation: el("#rp-remediation").value,
            lessons_learned: el("#rp-lessons").value,
          }),
        });
        statusEl.textContent = "Saved.";
        statusEl.className = "form-status is-success";
      } catch (err) {
        statusEl.textContent = err.message;
        statusEl.className = "form-status is-error";
      }
    });
  }

  // ------------------------------------------------------------------
  // Trends
  // ------------------------------------------------------------------
  el("#trend-range").addEventListener("change", loadTrends);

  async function loadTrends() {
    const days = el("#trend-range").value;
    const data = await api(`/api/trends?days=${days}`);
    renderTrendChart(data);
    renderTrendTotals(data.totals_by_type);
  }

  function renderTrendChart(data) {
    const canvas = el("#trend-chart");
    const emptyState = el("#trend-empty");

    if (data.by_bucket.length === 0) {
      emptyState.classList.remove("hidden");
      canvas.classList.add("hidden");
      if (state.chart) {
        state.chart.destroy();
        state.chart = null;
      }
      return;
    }
    emptyState.classList.add("hidden");
    canvas.classList.remove("hidden");

    const buckets = Array.from(
      new Set(data.by_bucket.map((r) => r.bucket_key)),
    ).sort();
    const bucketLabels = Object.fromEntries(
      data.by_bucket.map((r) => [r.bucket_key, r.bucket_label]),
    );
    const types = Array.from(
      new Set(data.by_bucket.map((r) => r.incident_type)),
    );

    const datasets = types.map((type, i) => {
      const byBucket = Object.fromEntries(
        data.by_bucket
          .filter((r) => r.incident_type === type)
          .map((r) => [r.bucket_key, r.c]),
      );
      return {
        label: type,
        data: buckets.map((b) => byBucket[b] || 0),
        backgroundColor: TYPE_COLORS[i % TYPE_COLORS.length],
        stack: "incidents",
      };
    });

    if (state.chart) state.chart.destroy();
    state.chart = new Chart(canvas.getContext("2d"), {
      type: "bar",
      data: { labels: buckets.map((b) => bucketLabels[b]), datasets },
      options: {
        responsive: true,
        scales: {
          x: { stacked: true, grid: { display: false } },
          y: { stacked: true, beginAtZero: true, ticks: { precision: 0 } },
        },
        plugins: {
          legend: {
            position: "bottom",
            labels: { boxWidth: 10, font: { size: 11 } },
          },
        },
      },
    });
  }

  function renderTrendTotals(totals) {
    const list = el("#trend-totals-list");
    list.innerHTML = "";
    if (totals.length === 0) {
      list.innerHTML = `<li class="totals-row"><span>No data in range.</span></li>`;
      return;
    }
    totals.forEach((t) => {
      const li = document.createElement("li");
      li.className = "totals-row";
      li.innerHTML = `<span>${escapeHtml(t.incident_type)}</span><span class="totals-count">${t.c}</span>`;
      list.appendChild(li);
    });
  }

  // ------------------------------------------------------------------
  // Boot
  // ------------------------------------------------------------------
  (async function boot() {
    await loadMeta();
    await loadIncidents();
  })();
})();