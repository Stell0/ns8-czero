# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
import importlib.util
import json
from pathlib import Path

import pytest

from czero_core.extraction_queue import ExtractionQueue, ExtractionPool

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('native_extraction_config',ROOT/'imageroot/bin/czero_extraction_config.py')
config=importlib.util.module_from_spec(spec); spec.loader.exec_module(config)


def test_omitted_configuration_preserves_all_existing_limits_and_opt_in():
    current={**config.DEFAULTS,'enabled':True,'workers':4,'document_workers':1,'space_workers':3}
    environment=config.encode(current)
    assert config.merge({},environment)==current
    assert config.read(environment)==current
    changed=config.merge({'extraction':{'workers':2}},environment)
    assert changed=={**current,'workers':2}
    assert config.encode(changed)['CZERO_EXTRACTION_MEMORY']=='2g'
    assert config.encode(changed)['CZERO_EXTRACTION_SWAP']=='4g'
    assert not config.read({})['enabled']


@pytest.mark.parametrize('change', [{'enabled':1},{'workers':True},{'workers':0},{'workers':5},
    {'space_workers':-1},{'document_workers':'2'},{'max_queued_units':199},
    {'max_staging_bytes':67108865},{'command':'untrusted'},None,[]])
def test_native_boundary_rejects_invalid_values_before_persistence(change):
    with pytest.raises(ValueError): config.merge({'extraction':change},{})


@pytest.mark.parametrize('environment', [{'CZERO_EXTRACTION_UNITS':'true'},
    {'CZERO_EXTRACTION_WORKERS':'2; command'},{'CZERO_EXTRACTION_WORKERS':'1000000000'}])
def test_invalid_saved_environment_fails_closed(environment):
    with pytest.raises(ValueError): config.read(environment)


def test_disabled_pool_does_no_io_and_worker_limits_are_not_cpu_quotas():
    queue=ExtractionQueue(None,None,None)
    assert ExtractionPool(queue).tick()=={'processed':0,'workers':0}
    for value in (True,0,5):
        with pytest.raises(ValueError): ExtractionPool(queue,workers=value)
    service=(ROOT/'imageroot/systemd/user/czero-extraction.service').read_text()
    assert '--memory=${CZERO_EXTRACTION_MEMORY}' in service and '--pids-limit=256' in service
    assert '--cpus' not in service and '--env-file=./environment' not in service
    assert 'ExecCondition=/usr/bin/test ${CZERO_EXTRACTION_UNITS} = 1' in service
    assert 'TimeoutStopSec=35' in service and 'podman stop --ignore -t 30' in service


def test_new_native_infrastructure_is_registered():
    manifest=json.loads((ROOT/'c0-upstream.json').read_text())
    entries={row['path']:row for row in manifest['files']}
    for path in ('imageroot/bin/czero_extraction_config.py','imageroot/systemd/user/czero-extraction.service',
                 'imageroot/systemd/user/czero-extraction.timer'):
        assert path in entries and (ROOT/path).is_file()
