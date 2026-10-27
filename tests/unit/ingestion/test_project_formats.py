# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
import pytest
from c0_ingest.errors import C0Error
from c0_projects.formats import load_data
from c0_projects.model import load_config


@pytest.mark.parametrize('body',[
    'name: one\nname: two','a: &item [1]\nb: *item','a: !!python/object/apply:os.system [echo forbidden]',
    'a: !!binary aGVsbG8=','a: .nan','1: value','a: ['*30+'0'+']'*30,
])
def test_untrusted_yaml_rejects_ambiguity_expansion_and_nondata(body):
    with pytest.raises(C0Error):load_data(body,'yaml')


def test_yaml_dates_stay_data_and_source_configuration_is_validated(tmp_path):
    assert load_data('day: 2026-10-25\nenabled: true\nname: "Ricerca"','yaml')=={
        'day':'2026-10-25','enabled':True,'name':'Ricerca'}
    path=tmp_path/'project.yml';path.write_text('''schema_version: 1
server_url: https://knowledge.example.org/mcp
project_space_id: 11111111-1111-4111-8111-111111111111
sources:
  - id: synthetic-docs
    adapter: http
    url: https://example.org/docs/
''')
    assert load_config(path)['sources'][0]['max_requests']==40
    with pytest.raises(C0Error):load_data('{"scope":"one","scope":"two"}','json')
