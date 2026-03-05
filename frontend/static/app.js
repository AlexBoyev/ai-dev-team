let chart = null;

function statusClass(status) {
  if (status === "working" || status === "in_progress") return "warn";
  if (status === "failed" || status === "rejected") return "bad";
  if (status === "completed") return "good";
  return "";
}

function pillForAgent(a) {
  const cls = statusClass(a.status);
  return `<span class="pill ${cls}">${a.status}</span>`;
}

function pillForTask(t) {
  const cls = statusClass(t.status);
  return `<span class="pill ${cls}">${t.status}</span>`;
}

function fmtTime(ts) {
  const d = new Date(ts * 1000);
  return d.toLocaleTimeString();
}

function renderAgents(agents) {
  const el = document.getElementById("agents");
  el.innerHTML = agents.map(a => `
    <div class="agent">
      <div class="agent-top">
        <div>
          <div class="agent-name">${a.name}</div>
          <div class="agent-role">${a.role}</div>
        </div>
        ${pillForAgent(a)}
      </div>
      <div class="small">Current task: <b>${a.current_task_id ?? "—"}</b></div>
      <div class="small">Last action: ${a.last_action ?? "—"}</div>
    </div>
  `).join("");
}

function renderTasks(tasks) {
  const tbody = document.querySelector("#tasksTable tbody");
  const sorted = [...tasks].sort((a,b) => a.id.localeCompare(b.id));
  tbody.innerHTML = sorted.map(t => `
    <tr>
      <td>${t.id}</td>
      <td>${t.title}</td>
      <td>${pillForTask(t)}</td>
      <td>${t.assigned_agent}</td>
      <td>${t.result ?? ""}</td>
    </tr>
  `).join("");
}

function renderLogs(logs) {
  const el = document.getElementById("logs");
  el.innerHTML = logs.map(e => `
    <div class="logline">
      <div class="lvl ${e.level}">${e.level}</div>
      <div class="src">${e.source}</div>
      <div class="msg">[${fmtTime(e.ts)}] ${e.message}</div>
    </div>
  `).join("");
  el.scrollTop = el.scrollHeight;
}

function countTaskStatuses(tasks) {
  const c = { pending:0, in_progress:0, completed:0, failed:0, rejected:0 };
  for (const t of tasks) c[t.status] = (c[t.status] ?? 0) + 1;
  return c;
}

function ensureChart(ctx, counts) {
  const labels = ["pending","in_progress","completed","failed","rejected"];
  const data = labels.map(k => counts[k] ?? 0);

  if (!chart) {
    chart = new Chart(ctx, {
      type: "bar",
      data: {
        labels,
        datasets: [{ label: "tasks", data }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: { y: { beginAtZero: true, ticks: { precision: 0 } } }
      }
    });
  } else {
    chart.data.datasets[0].data = data;
    chart.update();
  }
}

async function refresh() {
  const res = await fetch("/api/state");
  const state = await res.json();

  const badge = document.getElementById("runBadge");
  badge.textContent = state.run_in_progress ? "Running" : "Idle";
  badge.style.color = state.run_in_progress ? "#ffcf5a" : "#98a6c4";

  renderAgents(state.agents);
  renderTasks(state.tasks);
  renderLogs(state.logs);

  const counts = countTaskStatuses(state.tasks);
  ensureChart(document.getElementById("taskChart"), counts);

  document.getElementById("runBtn").disabled = !!state.run_in_progress;
}

async function runDemo() {
  await fetch("/api/run", { method: "POST" });
}

async function resetAll() {
  await fetch("/api/reset", { method: "POST" });
}

document.getElementById("runBtn").addEventListener("click", runDemo);
document.getElementById("resetBtn").addEventListener("click", resetAll);

refresh();
setInterval(refresh, 3000);