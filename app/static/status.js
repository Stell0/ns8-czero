// Copyright (C) 2026 C0 contributors
// SPDX-License-Identifier: GPL-3.0-or-later
const status = document.getElementById("database-status");
const refresh = document.getElementById("refresh-status");
let healthGeneration = 0;
async function checkHealth() {
  const generation = ++healthGeneration;
  refresh.disabled = true;
  try {
    const response = await fetch("./api/v1/health", { cache: "no-store" });
    const health = await response.json();
    if (generation !== healthGeneration) return;
    status.textContent = response.ok && health.status === "ok" && health.database.status === "ok" ? "Workspace ready" : "Workspace unavailable. Ask an administrator to check the service.";
  } catch {
    if (generation !== healthGeneration) return;
    status.textContent = "Application unavailable";
  } finally {
    if (generation === healthGeneration) refresh.disabled = false;
  }
}
refresh.addEventListener("click", checkHealth);
checkHealth();
