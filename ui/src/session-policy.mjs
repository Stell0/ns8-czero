// Copyright (C) 2026 C0 contributors
// SPDX-License-Identifier: GPL-3.0-or-later
export function sessionPolicyForm(value = {}) {
  return {
    absolute_seconds: String(value.absolute_seconds ?? 28800),
    idle_seconds: String(value.idle_seconds ?? 3600),
  };
}

export function sessionPolicyPayload(value) {
  const absolute_seconds = Number(value.absolute_seconds);
  const idle_seconds = Number(value.idle_seconds);
  if (
    !Number.isInteger(absolute_seconds) ||
    !Number.isInteger(idle_seconds) ||
    idle_seconds < 60 ||
    idle_seconds > absolute_seconds ||
    absolute_seconds > 86400
  ) {
    throw new Error("invalid_session_policy");
  }
  return { absolute_seconds, idle_seconds };
}
