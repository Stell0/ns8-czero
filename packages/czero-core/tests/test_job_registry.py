# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
import pytest

from czero_core.jobs import Handler, Registry, bounded_json, default_registry, empty_payload


@pytest.mark.parametrize("options", [
    {"name":"health", "max_attempts":0}, {"name":"health", "max_attempts":6},
    {"name":"health", "max_attempts":True}, {"name":"health", "timeout_seconds":0},
    {"name":"health", "timeout_seconds":31}, {"name":"health", "timeout_seconds":True},
    {"name":"x"*65}, {"name":"../exec"},
])
def test_handler_limits_and_names_are_checked(options):
    with pytest.raises(ValueError):Handler(execute=lambda *a: {}, **options)


def test_registry_rejects_unknown_duplicate_and_non_callable_handlers():
    handler=Handler("health",lambda *a:{})
    registry=Registry([handler])
    with pytest.raises(ValueError):registry.register(handler)
    with pytest.raises(ValueError):Handler("shell", "echo something")
    for name in ("os.system","__import__('os')"):
        with pytest.raises(ValueError):registry.get(name)
    assert registry.describe()==[{"name":"health","max_attempts":3,"timeout_seconds":10}]


@pytest.mark.parametrize("value", [[], "text", {"x":float("nan")}, {"x":object()}, {"x":"a"*16384}])
def test_bounded_payload_rejects_non_json_or_oversized_data(value):
    with pytest.raises(ValueError,match="invalid_payload"):bounded_json(value)


def test_bounded_payload_is_canonical_and_registered_defaults_reject_commands():
    assert bounded_json({"b":2,"a":"é"})=='{"a":"é","b":2}'
    assert [item["name"] for item in default_registry().describe()]==["health","maintenance"]
    with pytest.raises(ValueError):empty_payload({"command":"SELECT 1"})
