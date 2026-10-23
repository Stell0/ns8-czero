// Copyright (C) 2026 C0 contributors
// SPDX-License-Identifier: GPL-3.0-or-later
export function connectionPolicyForm(seconds = 2592000) {
  return String(seconds / 86400);
}

export function connectionPolicyPayload(value) {
  if (typeof value !== 'string' && typeof value !== 'number') {
    throw new Error('invalid_connection_policy');
  }
  const days = Number(value);
  if (!Number.isInteger(days) || days < 1 || days > 365) {
    throw new Error('invalid_connection_policy');
  }
  return days * 86400;
}
