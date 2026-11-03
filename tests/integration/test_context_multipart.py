# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
from uuid import UUID
import pytest
from sqlalchemy import text
from czero_core.current_content import ContentSuperseded
from test_full_documents import logical,publish,sample_connection,knowledge_http,space_http,transport,application


def test_current_logical_parent_has_exact_context_and_part_relative_citations(logical):
    client,definition,service,actor,path=logical
    body=('# Prerequisite\n\nUse K17.\n\n# Background\n\n'+'Unrelated material. '*9000+'\n\n'+
        '# Procedure\n\nRead [setup](#prerequisite), then turn clockwise.\n')
    saved,receipts=publish(client,definition,path,body)
    assert len(receipts)>=2
    outline=service.outline(actor,saved['id'])
    result=service.context_bundle(actor,[{'logical_document_id':saved['id'],'revision_id':outline['revision_id'],
        'selection_ids':['s3'],'reference_ids':['r0']}])
    assert [row['selection_id'] for row in result['sections']]==['s3','s1']
    assert result['sections'][0]['body']==body[body.index('# Procedure'):]
    for row in result['sections']:
        for citation in row['citations']:
            with service.database.engine.connect() as c:
                chunk=c.execute(text('SELECT body,start_offset,end_offset,content_hash FROM c0_chunks WHERE id=:id'),
                    {'id':UUID(citation['chunk_id'])}).mappings().one()
            assert chunk['content_hash']==citation['content_hash'] and chunk['start_offset']==citation['start_offset']
            assert chunk['body']==body[citation['document_start_offset']:citation['document_end_offset']]
    assert result['sections'][0]['citations'][0]['document_start_offset']>result['sections'][0]['citations'][0]['start_offset']
    publish(client,definition,path,body+'A changed observation.\n')
    with pytest.raises(ContentSuperseded): service.sections(actor,saved['id'],revision_id=outline['revision_id'],selection_ids=['s1'])
