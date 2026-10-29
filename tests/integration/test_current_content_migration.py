# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Upgrade a real independently installed released Core, with recoverable failure."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from uuid import UUID,uuid4

import pytest
from sqlalchemy import create_engine,text
from sqlalchemy.engine import make_url

from czero_core.access import AccessService
from czero_core.annotations import AnnotationService,ContentTarget
from czero_core.database import Database
from czero_core.documents import DocumentService
from czero_core.identity import VerifiedIdentity
from czero_core.jobs import default_registry
from czero_core.knowledge import KnowledgeService
from czero_core.migrate import migrate_database
from czero_core.retention import preflight
from czero_core.sources import OriginalStore,register_source_handlers


@pytest.fixture(scope='module')
def predecessor_python(tmp_path_factory):
    directory=tmp_path_factory.mktemp('independent-predecessor')
    python=directory/'venv/bin/python'
    supplied=os.getenv('CZERO_TEST_PREDECESSOR_PYTHON')
    if supplied:python=Path(supplied)
    else:
        for command in (['uv','venv','--python',sys.executable,str(directory/'venv')],
            ['uv','pip','install','--python',str(python),'czero-core @ git+https://github.com/Stell0/ns8-czero.git@3fb900e25cced88c25ca8b8dd2148ae911a31f00#subdirectory=packages/czero-core']):
            result=subprocess.run(command,capture_output=True,timeout=240,env={**os.environ,'UV_CACHE_DIR':str(directory/'cache')})
            (directory/'install.log').write_bytes(result.stdout+result.stderr)
            assert result.returncode==0,'Independent predecessor installation failed; inspect private install.log'
    probe=subprocess.run([str(python),'-I','-c',"import czero_core,importlib.metadata;print(importlib.metadata.version('czero-core'));print(czero_core.__file__)"],capture_output=True,text=True,timeout=20)
    assert probe.returncode==0 and probe.stdout.splitlines()[0]=='0.35.2'
    assert '/packages/czero-core/src/' not in probe.stdout
    return python


@pytest.fixture
def predecessor_database(predecessor_python,tmp_path):
    assert os.getenv('CZERO_TEST_DATABASE_URL'),'Disposable PostgreSQL is required'
    url=make_url(os.environ['CZERO_TEST_DATABASE_URL']);name='c0_content_upgrade_'+uuid4().hex
    admin=create_engine(url,hide_parameters=True)
    with admin.connect().execution_options(isolation_level='AUTOCOMMIT') as c:c.execute(text('CREATE DATABASE '+name))
    target=url.set(database=name).render_as_string(hide_password=False)
    database=Database(target)
    try:
        seed=Path(__file__).with_name('seed_previous_content.py')
        result=subprocess.run([str(predecessor_python),str(seed),str(tmp_path)],capture_output=True,timeout=120,
            env={**os.environ,'CZERO_DATABASE_URL':target})
        (tmp_path/'seed.log').write_bytes(result.stdout+result.stderr)
        assert result.returncode==0,'Released Core seed failed; inspect private seed.log'
        ids=json.loads((tmp_path/'identities.json').read_text())
        yield database,ids,tmp_path
    finally:
        database.close()
        with admin.connect().execution_options(isolation_level='AUTOCOMMIT') as c:c.execute(text('DROP DATABASE '+name+' WITH (FORCE)'))
        admin.dispose()


def test_released_upgrade_removes_all_automatic_history_and_preserves_current(predecessor_database):
    database,ids,path=predecessor_database
    with database.engine.connect() as c:
        c.execute(text('SET TRANSACTION READ ONLY'));report,_=preflight(c)
    assert not report['blocked'] and report['superseded_source_versions']==4
    assert report['affected_evidence_links']==1 and report['superseded_wiki_bodies']==2
    for _ in range(2):migrate_database(database)
    access=AccessService(database,ids['issuer'],UUID(ids['owner_key']))
    actor=access.resolve(VerifiedIdentity(ids['issuer'],'owner',ids['owner_key'],'owner','Owner',time.time()+600))
    reader=DocumentService(database,access).in_space(ids['space'])
    wiki=KnowledgeService(database,access).in_space(ids['space'])
    assert reader.read_document(actor,ids['source'])['body']=='CURRENT-SOURCE-B-UNIQUE'
    assert reader.read_document(actor,ids['parent'])['body']=='# Current multipart\n\nCURRENT-PART-1\nCURRENT-PART-2\n'
    assert reader.read_document(actor,ids['dated_source'])['body']=='CURRENT-INDEPENDENT-VERSION-14-MANUAL'
    assert wiki.get_page(actor,ids['archived'])['deleted']
    assert 'Intentional quotation: RETIRED-SOURCE-A-UNIQUE' in wiki.get_page(actor,ids['page'])['content']['body']
    claim=wiki.get_claim(actor,ids['claim'])
    assert claim['evidence_stale'] and claim['evidence'][0]['status']=='superseded' and claim['evidence'][0]['body'] is None
    annotation=AnnotationService(database,access).in_space(ids['space']).get(actor,ContentTarget('source_version',ids['retired_version'],1),'verification')
    assert annotation['status']=='stale' and not annotation['target_current']
    registry=default_registry();store=OriginalStore(path/'originals');register_source_handlers(registry,database,store)
    with database.engine.begin() as c:registry.get('source.cleanup').execute(c,{'version_id':str(UUID(int=0))})
    assert not store.path(ids['retired_version']).exists() and store.path(ids['current_version']).exists()
    assert not store.path(ids['obsolete_part']).exists()
    with database.engine.connect() as c:
        assert c.execute(text("SELECT count(*) FROM c0_objects WHERE type_name IN ('c0_project_source_snapshot_history_v1','c0_project_source_sync_history_v1')")).scalar_one()==0
        assert c.execute(text("SELECT count(*) FROM c0_wiki_revisions WHERE body='RETIRED-WIKI-A-UNIQUE'")).scalar_one()==0
        assert c.execute(text("SELECT count(*) FROM c0_knowledge_receipts WHERE result::text LIKE '%RETIRED-WIKI-A-UNIQUE%'")).scalar_one()==0
        assert c.execute(text('SELECT count(*) FROM c0_embeddings')).scalar_one()==0
        assert c.execute(text('SELECT count(*) FROM c0_source_versions WHERE id=:id'),{'id':ids['obsolete_part']}).scalar_one()==0
        assert c.execute(text("SELECT count(*) FROM c0_documents WHERE body LIKE '%OLD-REMOVED-LAST-PART%'")).scalar_one()==0
    with database.engine.begin() as c:
        c.execute(text("SET LOCAL c0.content_protocol='old'"))
        with pytest.raises(Exception,match='writer protocol changed'):
            with c.begin_nested():c.execute(text('UPDATE c0_sources SET title=title WHERE id=:id'),{'id':ids['source']})


def test_corrupt_parent_blocks_before_retirement_and_interruption_is_atomic(predecessor_database,monkeypatch):
    database,ids,_=predecessor_database
    with database.engine.begin() as c:
        parent=c.execute(text('SELECT data FROM c0_objects WHERE id=:id'),{'id':ids['parent']}).scalar_one()
        broken={**parent,'part_receipt_ids':[str(uuid4())]}
        c.execute(text('UPDATE c0_objects SET data=CAST(:data AS jsonb) WHERE id=:id'),{'id':ids['parent'],'data':json.dumps(broken)})
    with database.engine.connect() as c:
        report,_=preflight(c)
        assert report['blocked'] and report['diagnostics'][0]['document_id']==ids['parent']
    with pytest.raises(RuntimeError,match='preflight_blocked'):migrate_database(database)
    with database.engine.begin() as c:
        assert c.execute(text('SELECT version_num FROM alembic_version')).scalar_one()=='0022_remembered_browsers'
        c.execute(text('UPDATE c0_objects SET data=CAST(:data AS jsonb) WHERE id=:id'),{'id':ids['parent'],'data':json.dumps(parent)})
    import czero_core.retention as retention
    original=retention.convert
    def interrupted(connection,plan):original(connection,plan);raise RuntimeError('simulated_migration_interruption')
    monkeypatch.setattr(retention,'convert',interrupted)
    with pytest.raises(RuntimeError,match='simulated_migration_interruption'):migrate_database(database)
    with database.engine.connect() as c:
        assert c.execute(text('SELECT version_num FROM alembic_version')).scalar_one()=='0022_remembered_browsers'
        assert c.execute(text('SELECT 1 FROM c0_source_versions WHERE id=:id'),{'id':ids['retired_version']}).scalar_one()==1
    monkeypatch.setattr(retention,'convert',original)
    migrate_database(database)
    assert database.health()['status']=='ok'


def test_read_only_original_audit_blocks_ambiguous_files_without_deleting(predecessor_database):
    from czero_core.retention import preflight_originals
    database,ids,path=predecessor_database
    unknown=path/'originals'/('.'+uuid4().hex)
    unknown.write_text('Unidentified legacy crash staging')
    backup=path/'originals'/'operator-backup.txt';backup.write_text('Operator backup stays untouched')
    before={file.name:file.read_bytes() for file in (path/'originals').iterdir() if file.is_file()}
    with database.engine.connect() as connection:
        connection.execute(text('SET TRANSACTION READ ONLY'))
        report=preflight_originals(connection,path/'originals')
    assert report['blocked'] and report['unidentified_generated_files']==1
    assert any(row['reason']=='unidentified_generated_file_reconcile_outside_managed_store' for row in report['diagnostics'])
    assert before=={file.name:file.read_bytes() for file in (path/'originals').iterdir() if file.is_file()}
