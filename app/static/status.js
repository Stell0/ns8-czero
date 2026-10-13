// Copyright (C) 2026 C0 contributors
// SPDX-License-Identifier: GPL-3.0-or-later
const status = document.getElementById("database-status");
const refresh = document.getElementById("refresh-status");
async function checkHealth() {
  refresh.disabled = true;
  try {
    const response = await fetch("./api/v1/health", { cache: "no-store" });
    const health = await response.json();
    status.textContent = health.database.status === "ok" ? "Database ready" : "Database unavailable";
  } catch {
    status.textContent = "Application unavailable";
  } finally {
    refresh.disabled = false;
  }
}
refresh.addEventListener("click", checkHealth);
checkHealth();
