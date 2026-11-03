# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
from copy import deepcopy
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from benchmarks.ingestion import percentile,corpus,measure,source_proof
from benchmarks.selective_context import BODY,CASES,grade
from benchmarks.restart import validate_container,IMAGE
import pytest


def test_frozen_measurement_refuses_an_unowned_database_before_migration(tmp_path):
    with pytest.raises(ValueError,match='owned_random_database'):
        measure({},'postgresql+psycopg://fixture@127.0.0.1/live',tmp_path)
    with pytest.raises(ValueError,match='loopback'):
        measure({},'postgresql+psycopg://fixture@production.example.org/live',tmp_path)
    with pytest.raises(ValueError,match='frozen_source_drift'):
        measure({},'postgresql+psycopg://fixture@127.0.0.1/czero_eval_'+'0'*32,tmp_path)


def test_matching_version_cannot_hide_installed_source_drift(tmp_path,monkeypatch):
    import czero_core
    fake=tmp_path/'core';fake.mkdir();(fake/'__init__.py').write_text('')
    monkeypatch.setattr(czero_core,'__file__',str(fake/'__init__.py'))
    with pytest.raises(ValueError,match='installed_core_source_mismatch'):source_proof()


def test_corpus_is_frozen_and_small_sample_p95_uses_the_declared_nearest_rank():
    sha,values=corpus()
    assert len(sha)==64 and {'plain.txt','readable-100.pdf','structured.docx'}<=values.keys()
    assert percentile([1,3,2],.95)==3 and percentile([1,3,2],.5)==2


def test_restart_controller_requires_owned_label_image_and_exact_loopback_port():
    info={'Name':'c0-ingestion-restart-20261103','Id':'a'*64,'ImageName':IMAGE.replace(':0.8.7-pg17-bookworm',''),
        'Config':{'Labels':{'io.czero.disposable-ingestion':'true'}},
        'NetworkSettings':{'Ports':{'5432/tcp':[{'HostIp':'127.0.0.1','HostPort':'15437'}]}}}
    url='postgresql+psycopg://fixture@127.0.0.1:15437/postgres'
    assert validate_container(info,url)=='a'*64
    for key,value in [('Name','production-database'),('ImageName','unreviewed:latest'),('Config',{'Labels':{}})]:
        changed=deepcopy(info);changed[key]=value
        with pytest.raises(ValueError):validate_container(changed,url)
    with pytest.raises(ValueError,match='port_mismatch'):
        validate_container(info,'postgresql+psycopg://fixture@127.0.0.1:15436/postgres')


def observation():
    start=BODY.index('# Verification');body=BODY[start:]
    source={'document_id':'document','space_id':'selected'}
    citation={'source_id':'source','version_id':'version','document_id':'document','chunk_id':'chunk',
        'content_hash':'chunk-hash','source_hash':'original-hash','start_offset':start,'end_offset':len(BODY),'body':body}
    final={k:v for k,v in citation.items() if k!='body'}
    runner={'valid':True,'final':{'answer':'Red requires isolation and cooling. Never reset.','citations':[final]}}
    calls=[{'name':'source_document_sections_get','arguments':{'space_id':'selected'},
        'result':{'structuredContent':{'sections':[{'body':body,'citations':[final]}]}}}]
    return source,citation,runner,calls


def test_grade_requires_actual_observed_original_spans_and_exact_current_citations():
    source,citation,runner,calls=observation()
    assert grade('red-indicator',runner,calls,source,{'chunk':citation},{},{})['passed']
    assert not grade('red-indicator',runner,[],source,{'chunk':citation},{},{})['passed']
    bad=deepcopy(runner);bad['final']['citations'][0]['content_hash']='expired'
    assert not grade('red-indicator',bad,calls,source,{'chunk':citation},{},{})['citations_valid']
    partial=deepcopy(calls);partial[0]['result']['structuredContent']['sections'][0]['body']=CASES['red-indicator']['evidence'][0]
    result=grade('red-indicator',runner,partial,source,{'chunk':citation},{},{})
    assert result['covered']==1 and not result['complete_original_evidence']


def test_grade_rejects_wrong_space_writes_mutations_and_tool_errors():
    source,citation,runner,calls=observation()
    for name,space in [('source_document_sections_get','other'),('wiki_pages_create','selected')]:
        changed=deepcopy(calls);changed[0].update(name=name,arguments={'space_id':space})
        assert not grade('red-indicator',runner,changed,source,{'chunk':citation},{},{})['passed']
    assert not grade('red-indicator',runner,calls,source,{'chunk':citation},{},{'changed':1})['passed']
    calls[0]['result']['isError']=True
    assert not grade('red-indicator',runner,calls,source,{'chunk':citation},{},{})['passed']
