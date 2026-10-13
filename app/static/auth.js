// Copyright (C) 2026 C0 contributors
// SPDX-License-Identifier: GPL-3.0-or-later
const accountStatus = document.getElementById("account-status");
const signIn = document.getElementById("sign-in");
const signOut = document.getElementById("sign-out");
const sharing = document.getElementById("sharing");
const accounts = document.getElementById("accounts");
const sharingStatus = document.getElementById("sharing-status");
let csrfToken = null;

async function loadAccounts() {
  const response = await fetch("./api/v1/access/accounts", { cache: "no-store" });
  if (!response.ok) throw new Error("Cannot load shared access");
  const result = await response.json();
  accounts.replaceChildren();
  for (const account of result.accounts) {
    const row = document.createElement("tr");
    const name = document.createElement("td");
    name.textContent = account.display_name || account.username;
    const detail = document.createElement("small");
    detail.textContent = `${account.username} · last sign-in ${new Date(account.last_seen).toLocaleString()}`;
    name.append(detail);
    const access = document.createElement("td");
    const action = document.createElement("td");
    if (account.is_owner) {
      access.textContent = "Owner (Admin)";
    } else {
      const select = document.createElement("select");
      select.setAttribute("aria-label", `Access for ${account.username}`);
      for (const [value, label] of [["", "No access"], ["reader", "Reader"], ["editor", "Editor"], ["admin", "Admin"]]) {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = label;
        select.append(option);
      }
      select.value = account.role || "";
      const save = document.createElement("button");
      save.type = "button";
      save.textContent = "Save";
      save.setAttribute("aria-label", `Save access for ${account.username}`);
      save.addEventListener("click", async () => {
        save.disabled = true;
        try {
          const updated = await fetch(`./api/v1/access/accounts/${account.id}`, {
            method: "PUT", headers: { "Content-Type": "application/json", "X-C0-CSRF": csrfToken },
            body: JSON.stringify({ role: select.value || null }),
          });
          if (!updated.ok) throw new Error("Access was not saved");
          sharingStatus.textContent = "Access saved";
          await loadAccounts();
        } catch {
          sharingStatus.textContent = "Access was not saved. Refresh sign-in and try again.";
        } finally {
          save.disabled = false;
        }
      });
      access.append(select);
      action.append(save);
    }
    row.append(name, access, action);
    accounts.append(row);
  }
}

async function checkAccount() {
  try {
    const status = await (await fetch("./api/v1/auth/status", { cache: "no-store" })).json();
    if (!status.configured) {
      accountStatus.textContent = "Ask the NethServer administrator to configure sign-in.";
      return;
    }
    signIn.hidden = false;
    const response = await fetch("./api/v1/me", { cache: "no-store" });
    if (response.status === 401) {
      accountStatus.textContent = "Sign in to use C0.";
      return;
    }
    if (response.status === 403) {
      accountStatus.textContent = "Your account has no C0 access. Ask the owner to admit it.";
      return;
    }
    if (!response.ok) throw new Error("Sign-in unavailable");
    const user = await response.json();
    csrfToken = user.csrf_token;
    accountStatus.textContent = `Signed in as ${user.username} · ${user.is_owner ? "Owner (Admin)" : user.role}`;
    signIn.hidden = true;
    signOut.hidden = false;
    if (user.role === "admin") {
      sharing.hidden = false;
      await loadAccounts();
    }
  } catch {
    accountStatus.textContent = "Sign-in is unavailable. Try again later.";
  }
}

signOut.addEventListener("click", async () => {
  signOut.disabled = true;
  try {
    const response = await fetch("./auth/logout", { method: "POST", headers: { "X-C0-CSRF": csrfToken } });
    if (!response.ok) throw new Error("Sign-out unavailable");
    window.location.assign((await response.json()).logout_url);
  } catch {
    accountStatus.textContent = "Sign-out did not complete. Refresh and try again.";
    signOut.disabled = false;
  }
});
checkAccount();
