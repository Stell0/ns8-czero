# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""GitHub destination policy composed from the shared SDK client."""
import json
from pathlib import Path
from c0_ingest.client import C0 as SharedC0
from c0_ingest.errors import C0Error
from .state import atomic, now


class C0(SharedC0):
    def resolve_space(self, state_path, dry_run=False):
        saved = json.loads(Path(state_path).read_text()) if Path(state_path).exists() else None
        if saved and saved.get("identity_id") != self.profile["id"]:
            raise C0Error("Saved authenticated account ID mismatch")
        target = self.config.get("space_id")
        if saved and saved["space_id"] != target:
            raise C0Error("Configured space differs from the existing job; refusing replacement")
        space = self.select_space(target)
        if space["name"] != self.config["space_name"]:
            raise C0Error("Configured space name/readback mismatch")
        if not dry_run:
            atomic(state_path, {"space_id": self.space_id, "name": space["name"],
                                "identity_id": self.profile["id"], "verified_at": now()})
        return self.space_id


def inspect(config):
    client = C0(config["c0"])
    try:
        if config["c0"].get("space_id"):
            client.select_space(config["c0"]["space_id"])
        return {"status": "verified", "identity": client.profile["nickname"],
                "account_id": client.profile["id"], "operations": len(client.operations), "writes": client.writes}
    finally:
        client.close()
