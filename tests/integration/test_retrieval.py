# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
import os
from uuid import uuid4
import pytest
from sqlalchemy import text
from czero_core.retrieval import SearchService
from czero_core.identity import Actor, PermissionDenied, Role
from czero_core.migrate import migrate_database
from test_wiki import wiki, create_page
from test_sources import sources, upload, execute
from test_access import access, identity, record_unadmitted, account_named

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='isolated PostgreSQL required')


@pytest.fixture
def search(wiki, sources):
    yield SearchService(wiki[0].database,wiki[0].access),wiki,sources


def test_provider_free_search_sources_and_current_wiki_have_exact_stable_citations(search):
    service,wiki,source = search; query='retrievaltoken'+uuid4().hex
    page = create_page(wiki,body='Intro ' * 500 + query + ' café 東京')
    version = upload(source,data=('Raw '+query+' source evidence').encode());execute(source,'source.extract',version['id'])
    result = service.search(wiki[1],query)
    assert result['retrieval_method']=='text' and result['fallback_reason'] is None
    assert {h['kind'] for h in result['hits']}=={'chunk','wiki_revision'}
    page_hit=next(h for h in result['hits'] if h['kind']=='wiki_revision')
    assert page_hit['id']==page['content']['id'] and page_hit['wiki']['page_id']==page['id']
    assert query in page_hit['excerpt'] and page['content']['body'][page_hit['start_offset']:page_hit['end_offset']]==page_hit['excerpt']
    chunk=next(h for h in result['hits'] if h['kind']=='chunk')
    assert chunk['citation']['source_hash']==version['content_hash']
    assert chunk['id']==chunk['citation']['chunk_id'] and chunk['content_hash']==chunk['citation']['content_hash']
    assert service.search(wiki[1],query)==result
    assert service.search(wiki[1],query,kind='wiki')['hits']==[page_hit]
    assert service.search(wiki[1],query,limit=1)['hits']==result['hits'][:1]
    for mode in ('semantic','hybrid'):
        fallback=service.search(wiki[1],query,mode=mode)
        assert fallback['hits']==result['hits'] and fallback['fallback_reason']=='embeddings_not_configured'


def test_text_search_excludes_obsolete_wiki_and_archives_preserves_raw_history(search):
    service,wiki,source=search;query='historic'+uuid4().hex
    page=create_page(wiki,body=query)
    changed=wiki[0].update_page(wiki[1],page['id'],'New','New current body',expected_revision=1,idempotency_key='change')
    assert service.search(wiki[1],query)['hits']==[]
    assert wiki[0].get_page(wiki[1],page['id'],revision=1)['content']['body']==query
    query='archived'+uuid4().hex
    page2=create_page(wiki,body=query)
    version=upload(source,data=query.encode());execute(source,'source.extract',version['id'])
    assert len(service.search(wiki[1],query)['hits'])==2
    wiki[0].delete_page(wiki[1],page2['id'],expected_revision=1,idempotency_key='archive')
    source[0].delete(source[1],version['source_id'],expected_revision=1)
    assert service.search(wiki[1],query)['hits']==[]
    assert wiki[0].get_page(wiki[1],page2['id'],revision=1)['content']['body']==query


def test_search_roles_are_rechecked_and_invalid_options_are_bounded(search):
    service,wiki,_=search;acl=wiki[0].access
    record_unadmitted(acl,uuid4(),'retrieval-member')
    member=account_named(acl,wiki[1],'retrieval-member')
    for role in (Role.READER,Role.EDITOR,Role.ADMIN):
        acl.set_role(wiki[1],member['id'],role)
        assert service.search(Actor(member['id'],Role.READER),'anything')['retrieval_method']=='text'
    acl.set_role(wiki[1],member['id'],None)
    with pytest.raises(PermissionDenied):service.search(Actor(member['id'],Role.ADMIN),'anything')
    for options in ({'limit':True},{'limit':51},{'mode':'sql'},{'kind':'shell'}):
        with pytest.raises(ValueError):service.search(wiki[1],'anything',**options)
    for query in ('','a'*513,'bad\0query'):
        with pytest.raises(ValueError):service.search(wiki[1],query)


def test_wiki_fts_migration_repeats_and_uses_a_gin_index(search):
    service,wiki,_=search;row=create_page(wiki,body='indexed knowledge')
    migrate_database(service.database)
    assert service.search(wiki[1],'indexed knowledge')['hits'][0]['id']==row['content']['id']
    with service.database.engine.begin() as c:
        c.execute(text('SET LOCAL enable_seqscan=off'))
        plan=' '.join(r[0] for r in c.execute(text("EXPLAIN SELECT id FROM c0_wiki_revisions WHERE search_vector @@ websearch_to_tsquery('simple','indexed')")))
    assert 'c0_wiki_revisions_search' in plan
