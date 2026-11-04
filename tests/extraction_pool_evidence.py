# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Strict grading of actual native extraction/resource/restore observations."""
import math
import re

FIELDS={'stage','workers','units','body_hash_verified','staging_cleared','native_limits_verified',
    'backup_readback','ocr_pages','ocr_text_verified','memory_peak_bytes','parser_peak_rss_bytes','memory_limit_bytes','swap_limit_bytes','pids_limit','duration_seconds'}


def operation_error(phase,workers,stderr):
    assert phase in {'configuration','prepare','seed','configure','drain','journal','verify','reindex'}
    assert workers is None or (type(workers) is int and workers in (2,4))
    found=re.search(r'^Disposable extraction pool proof failed \(([A-Za-z]{1,64})\)$',stderr,re.M)
    known={'AssertionError','FileNotFoundError','JSONDecodeError','SourceConflict',
        'PermissionDenied','OperationalError','IntegrityError','ExtractionError','ValueError'}
    kind=found[1] if found and found[1] in known else 'unclassified'
    return f'Disposable native extraction operation failed (phase={phase}, workers={workers}, type={kind})'


def validate_reindex(value):
    assert type(value) is dict and set(value)=={'stage','workers','units','verified'},'Invalid explicit reindex evidence'
    assert value['stage']=='reindex' and type(value['workers']) is int and value['workers'] in (2,4)
    assert type(value['units']) is int and value['units']==9 and value['verified'] is True
    return value


def require_reindexes(values):
    assert type(values) is list and len(values)==2,'Both restored explicit reindexes are required'
    assert {validate_reindex(value)['workers'] for value in values}=={2,4},'Both restored explicit reindexes are required'
    return values


def validate_measurement(value):
    assert type(value) is dict and set(value)==FIELDS,'Invalid extraction pool evidence'
    stage=value['stage']; workers=value['workers']
    assert stage in ('seed','verify') and type(workers) is int and workers in (2,4)
    assert type(value['units']) is int and value['units']==9
    assert type(value['ocr_pages']) is int and value['ocr_pages']==1 and value['ocr_text_verified'] is True
    assert value['body_hash_verified'] is True and value['staging_cleared'] is True
    assert value['native_limits_verified'] is (stage=='seed') and value['backup_readback'] is (stage=='verify')
    if stage=='seed':
        memory=workers*1073741824
        assert all(type(value[k]) is int for k in ('parser_peak_rss_bytes','memory_limit_bytes','swap_limit_bytes','pids_limit'))
        assert value['memory_limit_bytes']==value['swap_limit_bytes']==memory
        assert value['memory_peak_bytes'] is None or (type(value['memory_peak_bytes']) is int and 0<value['memory_peak_bytes']<=memory)
        assert 0<value['parser_peak_rss_bytes']<=536870912 and value['pids_limit']==256
        elapsed=value['duration_seconds']
        assert type(elapsed) in (int,float) and math.isfinite(elapsed) and 0<elapsed<=130
    else:
        assert all(value[k] is None for k in ('memory_peak_bytes','parser_peak_rss_bytes','memory_limit_bytes','swap_limit_bytes','pids_limit','duration_seconds'))
    return value


def require_stages(values):
    seen=set()
    for value in values:
        validate_measurement(value)
        key=(value['stage'],value['workers'])
        assert key not in seen,'Duplicate extraction pool evidence'
        seen.add(key)
    assert seen=={('seed',2),('seed',4),('verify',2),('verify',4)},'Missing native extraction/restore stage'
    return values
