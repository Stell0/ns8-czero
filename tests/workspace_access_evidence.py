# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Strict nonprivate observations required from actual native access workflows."""
EXPECTED={
    'prepare':{'fresh_reader':True,'pending_request':True},
    'approved':{'allowed_scopes':['c0:read'],'user_role':'reader','metadata_verified':True},
    'declined':{'remaining_requests':1,'consented_connections':2},
    'disconnected':{'member_statuses':[200,401],'other_status':200,'refresh_status':400},
    'blocked':{'member_statuses':[401,401],'other_status':200,'blocked_signins':2,'blocked':True},
    'blocked_after_restart':{'member_statuses':[401,401],'other_status':200,'blocked_signins':2,'blocked':True,'restart_changed':True},
    'unblocked':{'user_role':'reader','member_statuses':[401,401],'fresh_login':True,'clients_disabled':True},
    'editor_permissions':{'user_role':'editor','workspace_status':403},
    'manage_permissions':{'user_role':'admin','workspace_status':200},
    'reader_permissions':{'user_role':'reader','workspace_status':403},
}


def validate_measurement(value):
    if not isinstance(value,dict) or type(value.get('phase')) is not str or value['phase'] not in EXPECTED:
        raise AssertionError('Invalid workspace access evidence')
    expected={'phase':value['phase'],**EXPECTED[value['phase']]}
    # JSON equality alone considers True == 1: require exact recursive types.
    def equal(actual,wanted):
        if type(actual) is not type(wanted):return False
        if isinstance(wanted,dict):return actual.keys()==wanted.keys() and all(equal(actual[k],v) for k,v in wanted.items())
        if isinstance(wanted,list):return len(actual)==len(wanted) and all(equal(a,b) for a,b in zip(actual,wanted))
        return actual==wanted
    if not equal(value,expected):raise AssertionError('Incomplete workspace access evidence')
    return dict(value)


def require_stages(values):
    checked=[validate_measurement(v) for v in values]
    if len(checked)!=len(EXPECTED) or {v['phase'] for v in checked}!=set(EXPECTED):
        raise AssertionError('All ten workspace access stages are required exactly once')
    return checked
