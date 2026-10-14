// Copyright (C) 2026 C0 contributors
// SPDX-License-Identifier: GPL-3.0-or-later
export function retrievalForm(saved = {}) {
  return {
    embedding: {
      enabled: false,
      endpoint: "",
      model: "",
      dimensions: 1536,
      send_dimensions: false,
      timeout: 3,
      ...saved.embedding,
      api_key: "",
      clear_api_key: false,
    },
    scorer: {
      mode: "off",
      endpoint: "",
      model: "",
      timeout: 3,
      threshold: 0.7,
      ...saved.scorer,
      api_key: "",
      clear_api_key: false,
    },
    limits: {
      max_limit: 50,
      candidates: 64,
      graph_depth: 3,
      scorer_candidates: 16,
      ...saved.limits,
    },
  };
}

export function retrievalPayload(form) {
  const result = {};
  for (const section of ["embedding", "scorer", "limits"]) {
    result[section] = {};
    for (const [key, value] of Object.entries(form[section])) {
      if (key === "api_key_configured") continue;
      result[section][key] = [
        "dimensions",
        "timeout",
        "threshold",
        "max_limit",
        "candidates",
        "graph_depth",
        "scorer_candidates",
      ].includes(key)
        ? Number(value)
        : value;
    }
  }
  return result;
}

export function clearRetrievalKeys(form) {
  for (const section of ["embedding", "scorer"]) {
    form[section].api_key = "";
    form[section].clear_api_key = false;
  }
}
