// Copyright (C) 2026 C0 contributors
// SPDX-License-Identifier: GPL-3.0-or-later
const el = id => document.getElementById(id);
let profile = null, definitions = [], current = null, offset = 0, listRequest = 0, detailRequest = 0, relationRequest = 0;
const canWrite = () => profile && ["editor", "admin"].includes(profile.role);
const splitList = value => value.split(",").map(s => s.trim()).filter(Boolean);

async function api(path, method = "GET", body = null) {
  const headers = {};
  if (method !== "GET") headers["X-C0-CSRF"] = profile.csrf_token;
  if (body !== null) headers["Content-Type"] = "application/json";
  const response = await fetch(`./api/v1/${path}`, { method, headers, cache: "no-store", body: body === null ? null : JSON.stringify(body) });
  if (!response.ok) {
    const messages = { 401: "Sign in again.", 403: "Your account cannot perform this operation.", 404: "This record or type no longer exists.", 409: "Conflict: the record changed or a unique value already exists. Load the saved version before retrying.", 503: "The service is unavailable. Try again later." };
    let message = messages[response.status] || "The request could not be completed.";
    if (response.status === 422) {
      const error = await response.json();
      message = typeof error.detail === "string" && error.detail.startsWith("record_invalid:") ? `Validation failed: ${error.detail.slice(15)}` : "Invalid data, schema, tags or limits. Check the type schema.";
    }
    throw new Error(message);
  }
  return response.status === 204 ? null : response.json();
}

async function loadTypes(preferred = null) {
  definitions = (await api("object-types")).types;
  for (const id of ["record-type", "relation-type"]) {
    const select = el(id), previous = preferred || select.value;
    select.replaceChildren();
    for (const type of definitions) {
      const option = document.createElement("option"); option.value = type.name; option.textContent = type.label; select.append(option);
    }
    if (definitions.some(t => t.name === previous)) select.value = previous;
  }
  el("new-record").disabled = definitions.length === 0;
}

async function loadRecords() {
  const request = ++listRequest, pageOffset = offset;
  const type = el("record-type").value;
  el("record-list").replaceChildren();
  if (!type) { el("records-status").textContent = "No types yet. Ask an Admin to register one."; return; }
  const result = await api(`objects?${new URLSearchParams({ type_name: type, limit: 50, offset: pageOffset })}`);
  if (request !== listRequest) return;
  el("record-list").replaceChildren();
  for (const record of result.objects) {
    const row = document.createElement("tr"), name = document.createElement("td"), revision = document.createElement("td"), tags = document.createElement("td"), button = document.createElement("button");
    button.type = "button"; button.textContent = typeof record.data.name === "string" ? record.data.name : record.id;
    button.addEventListener("click", () => selectRecord(record.id).catch(showListError)); name.append(button);
    revision.textContent = record.revision; tags.textContent = record.tags.join(", "); row.append(name, revision, tags); el("record-list").append(row);
  }
  el("records-previous").disabled = offset === 0;
  el("records-next").disabled = result.objects.length < 50;
  el("records-status").textContent = `${result.objects.length} records shown, starting at ${pageOffset + 1}. Type picker shows the first 100 types.`;
}
const showListError = error => { el("records-status").textContent = error.message; };

function displayRecord(record) {
  ++detailRequest;
  current = record;
  const type = definitions.find(t => t.name === (record ? record.type_name : el("record-type").value));
  el("record-detail").hidden = false; el("record-heading").textContent = record ? type.label : "New record";
  el("record-identity").textContent = record ? `${record.id} · revision ${record.revision}` : "Save to create a stable record ID.";
  el("record-schema").textContent = JSON.stringify(type.schema, null, 2);
  el("record-data").value = JSON.stringify(record ? record.data : {}, null, 2); el("record-data").readOnly = !canWrite();
  el("record-tags").value = record ? record.tags.join(", ") : ""; el("record-tags").readOnly = !canWrite();
  el("save-record").hidden = !canWrite(); el("delete-record").hidden = !canWrite() || !record;
  el("reload-record").hidden = !record; el("relation-form").hidden = !canWrite() || !record;
  el("record-status").textContent = ""; el("record-relations").replaceChildren();
}

async function loadRelations() {
  const request = ++relationRequest;
  if (!current) return;
  const objectId = current.id;
  const result = await api(`objects/${objectId}/relations`);
  if (request !== relationRequest || !current || current.id !== objectId) return;
  el("record-relations").replaceChildren();
  for (const relation of result.relations) {
    const li = document.createElement("li"), outgoing = relation.source_id === current.id, other = outgoing ? relation.target_id : relation.source_id;
    const link = document.createElement("button"); link.type = "button"; link.textContent = `${relation.kind} ${outgoing ? "→" : "←"} ${other}`;
    link.addEventListener("click", () => selectRecord(other).catch(showListError)); li.append(link);
    if (canWrite()) {
      const remove = document.createElement("button"); remove.type = "button"; remove.textContent = "Remove relation";
      remove.addEventListener("click", async () => { try { await api(`object-relations/${relation.id}`, "DELETE"); await loadRelations(); } catch (e) { el("record-status").textContent = e.message; } }); li.append(remove);
    }
    el("record-relations").append(li);
  }
}
async function selectRecord(id) {
  const request = ++detailRequest;
  const record = await api(`objects/${id}`);
  if (request !== detailRequest) return;
  if (!definitions.some(t => t.name === record.type_name)) {
    const definition = await api(`object-types/${encodeURIComponent(record.type_name)}`);
    if (request !== detailRequest) return;
    definitions.push(definition);
  }
  displayRecord(record); await loadRelations();
}

el("record-type").addEventListener("change", () => { offset = 0; ++detailRequest; current = null; el("record-detail").hidden = true; loadRecords().catch(showListError); });
el("refresh-records").addEventListener("click", () => loadRecords().catch(showListError));
el("records-previous").addEventListener("click", () => { offset = Math.max(0, offset - 50); loadRecords().catch(showListError); });
el("records-next").addEventListener("click", () => { offset += 50; loadRecords().catch(showListError); });
el("new-record").addEventListener("click", () => { displayRecord(null); el("record-data").focus(); });
el("reload-record").addEventListener("click", () => selectRecord(current.id).catch(e => { el("record-status").textContent = e.message; }));
el("record-form").addEventListener("submit", async event => {
  event.preventDefault(); el("save-record").disabled = true;
  const selected = detailRequest;
  try {
    const data = JSON.parse(el("record-data").value), tags = splitList(el("record-tags").value);
    const record = current ? await api(`objects/${current.id}`, "PUT", { data, tags, expected_revision: current.revision }) : await api("objects", "POST", { type_name: el("record-type").value, data, tags });
    if (selected === detailRequest) { displayRecord(record); el("record-status").textContent = "Record saved."; await loadRelations(); }
    await loadRecords();
  } catch (error) { el("record-status").textContent = error instanceof SyntaxError ? "Enter valid JSON." : error.message; }
  finally { el("save-record").disabled = false; }
});
el("delete-record").addEventListener("click", async () => {
  if (!current || !window.confirm("Delete this record and its relations?")) return;
  try { await api(`objects/${current.id}?expected_revision=${current.revision}`, "DELETE"); current = null; el("record-detail").hidden = true; await loadRecords(); } catch (error) { el("record-status").textContent = error.message; }
});
el("relation-form").addEventListener("submit", async event => {
  event.preventDefault();
  try { await api("object-relations", "POST", { source_id: current.id, source_type: current.type_name, target_id: el("relation-target").value, target_type: el("relation-type").value, kind: el("relation-kind").value }); await loadRelations(); el("record-status").textContent = "Relation saved."; } catch (error) { el("record-status").textContent = error.message; }
});
el("type-form").addEventListener("submit", async event => {
  event.preventDefault();
  try {
    const name = el("type-name").value;
    await api("object-types", "POST", { name, label: el("type-label").value, schema: JSON.parse(el("type-schema").value), unique_fields: splitList(el("type-unique").value) });
    await loadTypes(name); offset = 0; ++detailRequest; current = null; el("record-detail").hidden = true; await loadRecords(); el("type-status").textContent = "Type registered.";
  } catch (error) { el("type-status").textContent = error instanceof SyntaxError ? "Enter valid JSON Schema." : error.message; }
});
(async () => {
  try {
    profile = await api("me"); el("records-account").textContent = `Signed in as ${profile.username} · ${profile.role}`;
    el("records-workspace").hidden = false; el("new-record").hidden = !canWrite(); el("type-registration").hidden = profile.role !== "admin";
    await loadTypes(); await loadRecords();
  } catch (error) { el("records-account").textContent = error.message; el("records-signin").hidden = false; }
})();
