/**
 * StudyPilot front-end — talks to the Flask API.
 */

const state = {
    tasks: [],
    summary: {},
    plan: [],
};

const views = {
    dashboard: { title: "Dashboard", sub: "A live view of your academic workload." },
    tasks: { title: "Tasks", sub: "Add, edit, and filter everything on your plate." },
    plan: { title: "Study plan", sub: "Seven-day schedule from the planning agent." },
    agent: { title: "AI agent", sub: "Capture work in natural language or ask for guidance." },
};

function $(sel) {
    return document.querySelector(sel);
}

function showToast(message) {
    const el = $("#toast");
    el.textContent = message;
    el.classList.remove("hidden");
    clearTimeout(showToast._t);
    showToast._t = setTimeout(() => el.classList.add("hidden"), 3200);
}

async function fetchJSON(url, options = {}) {
    const res = await fetch(url, {
        headers: { "Content-Type": "application/json", ...options.headers },
        ...options,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
        throw new Error(data.error || res.statusText || "Request failed");
    }
    return data;
}

function priorityClass(p) {
    const key = (p || "low").toLowerCase();
    return `priority-${key}`;
}

function formatDue(due) {
    if (!due) return "No date";
    try {
        const d = new Date(due + "T12:00:00");
        return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
    } catch {
        return due;
    }
}

function applySummary(summary) {
    state.summary = summary || {};
    $("#kpi-pending").textContent = summary.pending_tasks ?? 0;
    $("#kpi-overdue").textContent = summary.overdue_tasks ?? 0;
    $("#kpi-week").textContent = summary.due_this_week ?? 0;
    $("#kpi-hours").textContent = summary.estimated_hours ?? 0;
}

async function refreshTasks() {
    const data = await fetchJSON("/api/tasks");
    state.tasks = data.tasks || [];
    applySummary(data.summary);
    renderTopPriorities();
    renderTaskTable();
}

async function refreshPlan() {
    const data = await fetchJSON("/api/plan");
    state.plan = data.plan || [];
    applySummary(data.summary);
    renderPlan();
    renderTodayFocus();
}

async function refreshHealth() {
    try {
        const h = await fetchJSON("/api/health");
        const badge = $("#agent-badge");
        if (h.openai) {
            badge.textContent = "OpenAI connected";
            badge.classList.remove("badge-muted");
            badge.classList.add("badge-live");
        } else {
            badge.textContent = "Rule-based agent (offline)";
            badge.classList.add("badge-muted");
            badge.classList.remove("badge-live");
        }
    } catch {
        /* ignore */
    }
}

function renderTopPriorities() {
    const el = $("#top-priorities");
    const pending = state.tasks.filter((t) => String(t.status).toLowerCase() !== "done");
    el.innerHTML = "";
    if (!pending.length) {
        el.innerHTML = '<div class="muted small">No pending tasks. Add one from the form or chat.</div>';
        return;
    }
    pending.slice(0, 5).forEach((t) => {
        const row = document.createElement("div");
        row.className = "list-item";
        row.innerHTML = `
            <div>
                <strong>${escapeHtml(t.title)}</strong>
                <div class="small muted">${escapeHtml(t.course || "")} · due ${formatDue(t.due_date)}</div>
            </div>
            <span class="tag ${priorityClass(t.priority)}">${escapeHtml(String(t.priority || "low"))} · ${t.score ?? 0}</span>
        `;
        el.appendChild(row);
    });
}

function renderTodayFocus() {
    const el = $("#today-focus");
    el.innerHTML = "";
    const today = state.plan[0];
    if (!today || !today.items || !today.items.length) {
        el.innerHTML = '<div class="muted small">No items scheduled for the first day yet.</div>';
        return;
    }
    today.items.forEach((t) => {
        const row = document.createElement("div");
        row.className = "list-item";
        row.innerHTML = `
            <div>
                <strong>${escapeHtml(t.title)}</strong>
                <div class="small muted">${t.estimated_hours ?? 0}h · ${escapeHtml(t.course || "")}</div>
            </div>
            <span class="tag">${formatDue(t.due_date)}</span>
        `;
        el.appendChild(row);
    });
}

function renderPlan() {
    const el = $("#plan-grid");
    el.innerHTML = "";
    if (!state.plan.length) {
        el.innerHTML = '<div class="muted small">No plan data.</div>';
        return;
    }
    state.plan.forEach((day) => {
        const card = document.createElement("div");
        card.className = "plan-day";
        const items = (day.items || [])
            .map((t) => `<li>${escapeHtml(t.title)} <span class="muted">(${t.estimated_hours ?? 0}h)</span></li>`)
            .join("");
        card.innerHTML = `
            <h3>${escapeHtml(day.weekday)}</h3>
            <div class="hours">${escapeHtml(day.date)} · ${day.scheduled_hours ?? 0}h scheduled</div>
            <ul>${items || '<li class="muted">Light day — catch up or rest.</li>'}</ul>
        `;
        el.appendChild(card);
    });
}

function escapeHtml(s) {
    return String(s)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}

function renderTaskTable() {
    const el = $("#task-table");
    const q = ($("#task-search")?.value || "").toLowerCase();
    const f = $("#task-filter")?.value || "all";
    let rows = [...state.tasks];
    if (q) {
        rows = rows.filter(
            (t) =>
                String(t.title).toLowerCase().includes(q) ||
                String(t.course || "").toLowerCase().includes(q)
        );
    }
    if (f !== "all") {
        rows = rows.filter((t) => String(t.status).toLowerCase() === f);
    }
    el.innerHTML = "";
    if (!rows.length) {
        el.innerHTML = '<div class="muted small">No tasks match your filters.</div>';
        return;
    }
    rows.forEach((t) => {
        const row = document.createElement("div");
        row.className = "task-row";
        row.innerHTML = `
            <div>
                <strong>${escapeHtml(t.title)}</strong>
                <div class="small muted">${escapeHtml(t.notes || "").slice(0, 120)}</div>
            </div>
            <div class="task-row-meta">
                <span class="tag">${escapeHtml(t.course || "—")}</span>
                <span class="tag">${formatDue(t.due_date)}</span>
                <span class="tag ${priorityClass(t.priority)}">${escapeHtml(t.priority || "low")}</span>
            </div>
            <div class="task-row-meta"><span class="tag">${t.estimated_hours ?? 0}h</span></div>
            <div class="task-row-meta">
                <select data-action="status" data-id="${escapeHtml(t.id)}" class="status-select">
                    <option value="pending" ${t.status === "pending" ? "selected" : ""}>Pending</option>
                    <option value="in_progress" ${t.status === "in_progress" ? "selected" : ""}>In progress</option>
                    <option value="done" ${t.status === "done" ? "selected" : ""}>Done</option>
                </select>
            </div>
            <div class="task-actions">
                <button class="ghost-btn" data-action="edit" data-id="${escapeHtml(t.id)}">Edit</button>
                <button class="ghost-btn" data-action="delete" data-id="${escapeHtml(t.id)}">Delete</button>
            </div>
        `;
        el.appendChild(row);
    });

    el.querySelectorAll('[data-action="edit"]').forEach((btn) =>
        btn.addEventListener("click", () => openEdit(btn.dataset.id))
    );
    el.querySelectorAll('[data-action="delete"]').forEach((btn) =>
        btn.addEventListener("click", () => removeTask(btn.dataset.id))
    );
    el.querySelectorAll(".status-select").forEach((sel) =>
        sel.addEventListener("change", (ev) => patchTask(sel.dataset.id, { status: ev.target.value }))
    );
}

async function patchTask(id, payload) {
    try {
        await fetchJSON(`/api/tasks/${id}`, { method: "PUT", body: JSON.stringify(payload) });
        await refreshTasks();
        await refreshPlan();
        showToast("Task updated");
    } catch (e) {
        showToast(e.message);
    }
}

async function removeTask(id) {
    if (!confirm("Delete this task?")) return;
    try {
        await fetchJSON(`/api/tasks/${id}`, { method: "DELETE" });
        await refreshTasks();
        await refreshPlan();
        showToast("Task removed");
    } catch (e) {
        showToast(e.message);
    }
}

function switchView(name) {
    document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
    document.querySelectorAll(".nav-item").forEach((n) => n.classList.remove("active"));
    const section = $(`#view-${name}`);
    if (section) section.classList.add("active");
    const meta = views[name] || views.dashboard;
    $("#view-title").textContent = meta.title;
    $("#view-sub").textContent = meta.sub;
    document.querySelectorAll(".nav-item").forEach((btn) => {
        if (btn.dataset.view === name) btn.classList.add("active");
    });
    if (name === "plan") {
        refreshPlan().catch((e) => showToast(e.message));
    }
}

function openModal() {
    $("#task-modal").classList.remove("hidden");
}

function closeModal() {
    $("#task-modal").classList.add("hidden");
}

function resetTaskForm() {
    const form = $("#task-form");
    form.reset();
    form.querySelector('[name="id"]').value = "";
    $("#modal-title").textContent = "New task";
}

function openEdit(id) {
    const t = state.tasks.find((x) => x.id === id);
    if (!t) return;
    const form = $("#task-form");
    form.querySelector('[name="id"]').value = t.id;
    form.querySelector('[name="title"]').value = t.title || "";
    form.querySelector('[name="course"]').value = t.course || "";
    form.querySelector('[name="due_date"]').value = (t.due_date || "").slice(0, 10);
    form.querySelector('[name="estimated_hours"]').value = t.estimated_hours ?? 2;
    form.querySelector('[name="weight"]').value = t.weight ?? 10;
    form.querySelector('[name="difficulty"]').value = t.difficulty ?? 3;
    form.querySelector('[name="notes"]').value = t.notes || "";
    form.querySelector('[name="status"]').value = t.status || "pending";
    $("#modal-title").textContent = "Edit task";
    openModal();
}

function appendChat(role, html) {
    const log = $("#chat-log");
    const div = document.createElement("div");
    div.className = `bubble ${role}`;
    div.innerHTML = html;
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
}

async function sendAgentMessage(text) {
    const data = await fetchJSON("/api/agent", {
        method: "POST",
        body: JSON.stringify({ message: text }),
    });
    state.tasks = data.tasks || [];
    applySummary(data.summary);
    renderTopPriorities();
    renderTaskTable();
    renderPlan();
    renderTodayFocus();

    const a = data.agent || {};
    let extra = "";
    if (a.suggestions && a.suggestions.length) {
        extra += `<div class="sub">${escapeHtml(a.suggestions.join(" · "))}</div>`;
    }
    if (a.plan && a.plan.length) {
        const first = a.plan[0];
        const lines = (first.items || [])
            .slice(0, 4)
            .map((t) => escapeHtml(t.title))
            .join(", ");
        extra += `<div class="sub"><strong>First day (${escapeHtml(first.weekday)}):</strong> ${lines || "Open the Study Plan tab for the full week."}</div>`;
    }
    appendChat("assistant", `${escapeHtml(a.reply || "")}${extra}`);
}

function init() {
    document.querySelectorAll(".nav-item").forEach((btn) =>
        btn.addEventListener("click", () => switchView(btn.dataset.view))
    );

    $("#open-task-form")?.addEventListener("click", () => {
        resetTaskForm();
        openModal();
    });
    $("#modal-close")?.addEventListener("click", closeModal);
    $("#modal-cancel")?.addEventListener("click", closeModal);
    $("#task-modal")?.addEventListener("click", (e) => {
        if (e.target.id === "task-modal") closeModal();
    });

    $("#task-form")?.addEventListener("submit", async (e) => {
        e.preventDefault();
        const form = e.target;
        const id = form.querySelector('[name="id"]').value;
        const payload = {
            title: form.title.value,
            course: form.course.value,
            due_date: form.due_date.value || null,
            estimated_hours: parseFloat(form.estimated_hours.value),
            weight: parseFloat(form.weight.value),
            difficulty: parseInt(form.difficulty.value, 10),
            notes: form.notes.value,
            status: form.status.value,
        };
        try {
            if (id) {
                await fetchJSON(`/api/tasks/${id}`, { method: "PUT", body: JSON.stringify(payload) });
                showToast("Task saved");
            } else {
                await fetchJSON("/api/tasks", { method: "POST", body: JSON.stringify(payload) });
                showToast("Task created");
            }
            closeModal();
            await refreshTasks();
            await refreshPlan();
        } catch (err) {
            showToast(err.message);
        }
    });

    $("#task-search")?.addEventListener("input", () => renderTaskTable());
    $("#task-filter")?.addEventListener("change", () => renderTaskTable());

    $("#reset-btn")?.addEventListener("click", async () => {
        if (!confirm("Reset all tasks to the demo set?")) return;
        try {
            await fetchJSON("/api/tasks/reset", { method: "POST", body: JSON.stringify({}) });
            showToast("Demo data restored");
            await refreshTasks();
            await refreshPlan();
            $("#chat-log").innerHTML = "";
        } catch (e) {
            showToast(e.message);
        }
    });

    $("#chat-form")?.addEventListener("submit", async (e) => {
        e.preventDefault();
        const input = $("#chat-message");
        const text = (input.value || "").trim();
        if (!text) return;
        input.value = "";
        appendChat("user", escapeHtml(text));
        try {
            await sendAgentMessage(text);
        } catch (err) {
            appendChat("assistant", escapeHtml(err.message));
        }
    });

    document.querySelectorAll(".chip").forEach((chip) =>
        chip.addEventListener("click", async () => {
            const prompt = chip.dataset.prompt || "";
            if (!prompt) return;
            appendChat("user", escapeHtml(prompt));
            try {
                await sendAgentMessage(prompt);
            } catch (err) {
                appendChat("assistant", escapeHtml(err.message));
            }
        })
    );

    refreshHealth();
    refreshTasks()
        .then(() => refreshPlan())
        .catch((e) => showToast(e.message));
}

document.addEventListener("DOMContentLoaded", init);
