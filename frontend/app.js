const API_BASE = "http://127.0.0.1:8000/api";

let employees = [];
let currentEmployee = null;
let currentRole = "EMPLOYEE";
let leaveTypes = [];

// DOM Elements
const userSelect = document.getElementById("userSelect");
const roleBadge = document.getElementById("roleBadge");
const leaveTypeSelect = document.getElementById("leaveTypeSelect");
const durationDisplay = document.getElementById("durationDisplay");
const startDateInput = document.getElementById("startDateInput");
const endDateInput = document.getElementById("endDateInput");
const pendingBadge = document.getElementById("pendingBadge");
const toast = document.getElementById("toast");

// Initialize application
document.addEventListener("DOMContentLoaded", async () => {
  initDateSelectors();
  await loadInitialData();
});

function initDateSelectors() {
  const now = new Date();
  const todayStr = now.toISOString().split("T")[0];
  startDateInput.min = todayStr;
  endDateInput.min = todayStr;

  // Populate report dropdowns
  const mSelect = document.getElementById("reportMonthSelect");
  const ySelect = document.getElementById("reportYearSelect");
  const months = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
  ];
  
  mSelect.innerHTML = months.map((m, idx) => 
    `<option value="${idx + 1}" ${idx === now.getMonth() ? "selected" : ""}>${m}</option>`
  ).join("");

  const currentYear = now.getFullYear();
  ySelect.innerHTML = [currentYear - 1, currentYear, currentYear + 1].map(y => 
    `<option value="${y}" ${y === currentYear ? "selected" : ""}>${y}</option>`
  ).join("");
}

async function loadInitialData() {
  try {
    const [empRes, typeRes] = await Promise.all([
      fetch(`${API_BASE}/employees`),
      fetch(`${API_BASE}/leave-types`)
    ]);

    employees = await empRes.json();
    leaveTypes = await typeRes.json();

    // Populate user switcher
    userSelect.innerHTML = employees.map(e => 
      `<option value="${e.id}">${e.name} (${e.role || "EMPLOYEE"} - ${e.department || "Staff"})</option>`
    ).join("");

    userSelect.addEventListener("change", (e) => {
      onUserChanged(Number(e.target.value));
    });

    // Populate leave types
    leaveTypeSelect.innerHTML = leaveTypes.map(t => 
      `<option value="${t.name}">${t.name} (Max ${t.default_days_allowed}d)</option>`
    ).join("");

    if (employees.length > 0) {
      onUserChanged(employees[0].id);
    }
  } catch (err) {
    showToast("Error connecting to backend API: " + err.message, "error");
  }
}

async function onUserChanged(empId) {
  currentEmployee = employees.find(e => e.id === empId);
  if (!currentEmployee) return;

  currentRole = (currentEmployee.role || "EMPLOYEE").toUpperCase();
  roleBadge.textContent = currentRole === "HR" ? "HR Admin View" : "Employee View";
  roleBadge.className = `role-badge ${currentRole.toLowerCase()}`;

  // Automatically switch tab based on role
  if (currentRole === "HR") {
    switchView("hr");
  } else {
    switchView("employee");
  }

  await refreshAll();
}

async function refreshAll() {
  if (currentEmployee) {
    await loadEmployeeDashboard(currentEmployee.id);
  }
  await loadHrData();
}

// ----------------- TAB SWITCHING -----------------
function switchView(viewName) {
  document.getElementById("viewEmployee").style.display = viewName === "employee" ? "block" : "none";
  document.getElementById("viewHr").style.display = viewName === "hr" ? "block" : "none";
  document.getElementById("viewReports").style.display = viewName === "reports" ? "block" : "none";

  document.getElementById("tabEmployee").classList.toggle("active", viewName === "employee");
  document.getElementById("tabHr").classList.toggle("active", viewName === "hr");
  document.getElementById("tabReports").classList.toggle("active", viewName === "reports");

  if (viewName === "reports") {
    loadMonthlyReport();
  }
}

// ----------------- EMPLOYEE DASHBOARD -----------------
async function loadEmployeeDashboard(empId) {
  try {
    const res = await fetch(`${API_BASE}/employees/${empId}`);
    if (!res.ok) throw new Error("Failed to fetch employee details");
    const data = await res.json();

    // Render Balances
    const container = document.getElementById("balanceCards");
    container.innerHTML = data.balances.map(b => `
      <div class="kpi-card glass-panel" style="--kpi-glow: rgba(56, 189, 248, 0.25);">
        <div class="kpi-title">
          <span>${b.leave_type}</span>
          <span style="font-size: 0.75rem; color: var(--primary);">Available</span>
        </div>
        <div class="kpi-value">${b.remaining_days} <span style="font-size: 1rem; color: var(--text-dim); font-weight: normal;">days</span></div>
        <div class="kpi-subtext">Total: ${b.total_days} | Used: ${b.used_days}</div>
      </div>
    `).join("");

    // Render History
    const historyRes = await fetch(`${API_BASE}/leave-requests?employee_id=${empId}`);
    const history = await historyRes.json();
    const historyBody = document.getElementById("employeeHistoryBody");

    if (history.length === 0) {
      historyBody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--text-dim);">No leave applications yet.</td></tr>`;
      return;
    }

    historyBody.innerHTML = history.map(r => `
      <tr>
        <td>#${r.request_id}</td>
        <td><strong>${r.leave_type}</strong></td>
        <td>${r.start_date}</td>
        <td>${r.end_date}</td>
        <td>${r.days} d</td>
        <td>${escapeHtml(r.reason || "-")}</td>
        <td><span class="status-pill ${r.status.toLowerCase()}">${r.status}</span></td>
        <td style="color: var(--text-muted);">${escapeHtml(r.decision_notes || "-")}</td>
      </tr>
    `).join("");
  } catch (err) {
    console.error(err);
  }
}

function calculateDays() {
  const s = startDateInput.value;
  const e = endDateInput.value;
  if (s && e) {
    const d1 = new Date(s);
    const d2 = new Date(e);
    const diffTime = d2 - d1;
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24)) + 1;
    if (diffDays > 0) {
      durationDisplay.value = `${diffDays} day${diffDays > 1 ? "s" : ""}`;
    } else {
      durationDisplay.value = "Invalid date range";
    }
  }
}

async function handleApplyLeave(event) {
  event.preventDefault();
  if (!currentEmployee) return;

  const leave_type_name = leaveTypeSelect.value;
  const start_date = startDateInput.value;
  const end_date = endDateInput.value;
  const reason = document.getElementById("reasonInput").value;

  const btn = document.getElementById("btnSubmitLeave");
  btn.disabled = true;
  btn.textContent = "Submitting...";

  try {
    const res = await fetch(`${API_BASE}/leave-requests`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        employee_id: currentEmployee.id,
        leave_type_name,
        start_date,
        end_date,
        reason
      })
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Error submitting leave request");
    }

    showToast("Leave request submitted for HR approval!", "success");
    document.getElementById("applyLeaveForm").reset();
    durationDisplay.value = "0 days";

    await refreshAll();
  } catch (err) {
    showToast(err.message, "error");
  } finally {
    btn.disabled = false;
    btn.textContent = "Submit Request";
  }
}

// ----------------- HR DASHBOARD -----------------
async function loadHrData() {
  try {
    const res = await fetch(`${API_BASE}/leave-requests`);
    const all = await res.json();

    const pending = all.filter(r => r.status === "PENDING");
    const history = all.filter(r => r.status !== "PENDING");

    // Update Pending badge
    if (pending.length > 0) {
      pendingBadge.style.display = "inline-block";
      pendingBadge.textContent = pending.length;
    } else {
      pendingBadge.style.display = "none";
    }

    // Pending Table
    const pBody = document.getElementById("hrPendingBody");
    if (pending.length === 0) {
      pBody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: var(--text-dim); padding: 2rem;">No pending approvals! All caught up.</td></tr>`;
    } else {
      pBody.innerHTML = pending.map(r => `
        <tr>
          <td>#${r.request_id}</td>
          <td><strong>${r.employee_name}</strong></td>
          <td>${r.department || "-"}</td>
          <td>${r.leave_type}</td>
          <td>${r.start_date} → ${r.end_date}</td>
          <td><span style="font-weight: 700;">${r.days}</span> days</td>
          <td style="max-width: 180px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${escapeHtml(r.reason || "-")}</td>
          <td style="color: var(--text-dim); font-size: 0.8rem;">${r.applied_at ? r.applied_at.substring(0, 10) : "-"}</td>
          <td>
            <div style="display: flex; gap: 0.4rem;">
              <button class="btn btn-success btn-sm" onclick="handleDecision(${r.request_id}, 'APPROVED')">Approve</button>
              <button class="btn btn-danger btn-sm" onclick="handleDecision(${r.request_id}, 'REJECTED')">Reject</button>
            </div>
          </td>
        </tr>
      `).join("");
    }

    // Historical Table
    const hBody = document.getElementById("hrHistoryBody");
    hBody.innerHTML = history.map(r => `
      <tr>
        <td>#${r.request_id}</td>
        <td>${r.employee_name}</td>
        <td>${r.department || "-"}</td>
        <td>${r.leave_type}</td>
        <td>${r.start_date} → ${r.end_date} (${r.days}d)</td>
        <td><span class="status-pill ${r.status.toLowerCase()}">${r.status}</span></td>
        <td style="color: var(--text-muted);">${escapeHtml(r.decision_notes || "-")}</td>
      </tr>
    `).join("");
  } catch (err) {
    console.error("Error loading HR data:", err);
  }
}

async function handleDecision(requestId, status) {
  const notes = prompt(`Optional decision comment for ${status}:`, status === "APPROVED" ? "Approved by HR" : "Rejected");
  if (notes === null) return; // user cancelled prompt

  try {
    const res = await fetch(`${API_BASE}/leave-requests/${requestId}/status`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status, notes })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Error updating request status");

    showToast(`Request #${requestId} has been ${status}!`, "success");
    await refreshAll();
  } catch (err) {
    showToast(err.message, "error");
  }
}

// ----------------- REPORTS & CSV EXPORT -----------------
async function loadMonthlyReport() {
  const month = document.getElementById("reportMonthSelect").value;
  const year = document.getElementById("reportYearSelect").value;

  try {
    const res = await fetch(`${API_BASE}/reports/monthly?year=${year}&month=${month}`);
    const data = await res.json();

    // Analytics KPIs
    const kpiGrid = document.getElementById("analyticsKpiGrid");
    kpiGrid.innerHTML = `
      <div class="kpi-card glass-panel" style="--kpi-glow: rgba(56, 189, 248, 0.25);">
        <div class="kpi-title">Total Applications</div>
        <div class="kpi-value">${data.total_requests}</div>
        <div class="kpi-subtext">In ${data.month_name} ${data.year}</div>
      </div>
      <div class="kpi-card glass-panel" style="--kpi-glow: rgba(16, 185, 129, 0.25);">
        <div class="kpi-title">Approved Absent Days</div>
        <div class="kpi-value">${data.total_days_approved} <span style="font-size: 1rem; font-weight: normal;">days</span></div>
        <div class="kpi-subtext">Productivity impact metric</div>
      </div>
      <div class="kpi-card glass-panel" style="--kpi-glow: rgba(245, 158, 11, 0.25);">
        <div class="kpi-title">Pending Decisions</div>
        <div class="kpi-value">${data.status_counts.PENDING || 0}</div>
        <div class="kpi-subtext">Awaiting HR action</div>
      </div>
    `;

    // Department Breakdown
    const deptDiv = document.getElementById("deptBreakdown");
    const depts = Object.entries(data.department_usage);
    if (depts.length === 0) {
      deptDiv.innerHTML = `<p style="color: var(--text-dim); font-size: 0.9rem;">No approved absences recorded.</p>`;
    } else {
      deptDiv.innerHTML = depts.map(([d, days]) => `
        <div style="display: flex; justify-content: space-between; margin-bottom: 0.6rem; font-size: 0.9rem;">
          <span>${d}</span>
          <strong>${days} days</strong>
        </div>
      `).join("");
    }

    // Leave Type Breakdown
    const typeDiv = document.getElementById("typeBreakdown");
    const types = Object.entries(data.type_usage);
    if (types.length === 0) {
      typeDiv.innerHTML = `<p style="color: var(--text-dim); font-size: 0.9rem;">No approved absences recorded.</p>`;
    } else {
      typeDiv.innerHTML = types.map(([t, days]) => `
        <div style="display: flex; justify-content: space-between; margin-bottom: 0.6rem; font-size: 0.9rem;">
          <span>${t}</span>
          <strong>${days} days</strong>
        </div>
      `).join("");
    }

    // Records Table
    const rTable = document.getElementById("reportTableBody");
    if (data.records.length === 0) {
      rTable.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--text-dim); padding: 1.5rem;">No records for ${data.month_name} ${data.year}.</td></tr>`;
    } else {
      rTable.innerHTML = data.records.map(r => `
        <tr>
          <td>#${r.Request_ID}</td>
          <td><strong>${r.Employee_Name}</strong></td>
          <td>${r.Department}</td>
          <td>${r.Leave_Type}</td>
          <td>${r.Start_Date}</td>
          <td>${r.End_Date}</td>
          <td>${r.Days} d</td>
          <td><span class="status-pill ${r.Status.toLowerCase()}">${r.Status}</span></td>
        </tr>
      `).join("");
    }
  } catch (err) {
    showToast("Error loading monthly report: " + err.message, "error");
  }
}

function downloadCsv() {
  const month = document.getElementById("reportMonthSelect").value;
  const year = document.getElementById("reportYearSelect").value;
  window.open(`${API_BASE}/reports/monthly?year=${year}&month=${month}&download=true`, "_blank");
}

// ----------------- UTILS -----------------
function showToast(msg, type = "success") {
  toast.textContent = msg;
  toast.className = `toast show ${type}`;
  setTimeout(() => {
    toast.className = "toast";
  }, 4000);
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
