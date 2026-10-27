# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
from uuid import uuid4
import pytest
from c0_ingest.errors import C0Error
from c0_projects.exporting import export_project,verify_export
from c0_projects.model import Item,sha
from c0_projects.publish import parts,sync_part
from test_ingestion_samples_http import sample_connection
from test_knowledge_http import knowledge_http
from test_mcp_http import transport
from test_spaces_http import space_http
from test_auth_http import application
from test_project_ingestion_http import setup


def test_actual_sdk_export_is_deterministic_private_and_detects_tampering(sample_connection,knowledge_http,tmp_path):
    config,_=sample_connection;client,definition=setup(config)
    def call(name,**values):return client.call(name,data={**values,'idempotency_key':uuid4().hex})
    try:
        receipt=sync_part(client,next(parts(Item('documents','export.md','Original export evidence',b'Original retained evidence.'))),
            tmp_path/'source.json',definition_hash=sha(definition),attempts=4,seconds=0)
        document=client.call('documents_get',version_id=receipt['version_id'])
        chunk=client.call('document_chunks_list',document_id=document['id'])['chunks'][0]
        entity=call('entities_create',kind='concept',label='Synthetic export anchor',aliases=['Export alias'])
        claim=call('claims_create',entity_id=entity['id'],predicate='supports',value={'synthetic':True},evidence_chunk_ids=[chunk['id']])
        wiki=call('wiki_pages_create',slug='export/learning',title='Export learning',body='# Original Markdown\n\nA retained learning.',metadata={})
        before=client.writes
        one=export_project(client,tmp_path/'one');two=export_project(client,tmp_path/'two')
        assert one['status']==two['status']=='VALIDATED' and one['manifest_hash']==two['manifest_hash']
        assert client.writes==before and one['writes_c0']==0
        assert (tmp_path/'one').stat().st_mode&0o777==0o700
        assert all(path.stat().st_mode&0o777==0o600 for path in (tmp_path/'one').rglob('*') if path.is_file())
        saved=tmp_path/'one/wiki'/wiki['id']/'revisions/1.md'
        assert saved.read_text()=='# Original Markdown\n\nA retained learning.'
        assert verify_export(tmp_path/'one')['status']=='VALIDATED'
        saved.write_text('Changed outside C0')
        with pytest.raises(C0Error):verify_export(tmp_path/'one')
        with pytest.raises(FileExistsError):export_project(client,tmp_path/'two')
    finally:client.close()


def test_export_detects_concurrent_changes_and_keeps_a_partial_receipt(sample_connection,knowledge_http,tmp_path,monkeypatch):
    config,_=sample_connection;client,_=setup(config);original=client.call;changed=[]
    def changing(name,**arguments):
        if name=='project_export_get' and arguments['kind']=='entities' and not changed:
            changed.append(True);original('wiki_pages_create',data={'slug':'concurrent/export','title':'Concurrent edit',
                'body':'# A real concurrent synthetic write','metadata':{},'idempotency_key':uuid4().hex})
        return original(name,**arguments)
    try:
        monkeypatch.setattr(client,'call',changing)
        result=export_project(client,tmp_path/'partial')
        assert result['status']=='PARTIAL' and (tmp_path/'partial/partial.json').is_file()
        assert not (tmp_path/'partial/manifest.sha256').exists()
        monkeypatch.setattr(client,'call',original)
        assert export_project(client,tmp_path/'recovered')['status']=='VALIDATED'
    finally:client.close()
