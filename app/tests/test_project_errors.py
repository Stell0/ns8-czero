# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
from czero_app.project_errors import mcp_project_error


def test_project_errors_are_fixed_and_never_copy_private_detail():
    assert mcp_project_error('project_run_claim',409,'project_conflict')==('project_conflict',409)
    for detail in ('private lease payload',{'private':'detail'},None):
        assert mcp_project_error('project_run_claim',409,detail)==('service_unavailable',503)
    assert mcp_project_error('unregistered_project_operation',409,'project_conflict') is None
