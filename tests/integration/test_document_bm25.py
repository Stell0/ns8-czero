# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
from test_current_content_migration import predecessor_python
from previous_content_services import historical_space_authorization
import math
import os
from uuid import uuid4

import pytest
from sqlalchemy import text

from czero_core.bm25 import query_groups, RANKER_VERSION
from czero_core.retrieval import reciprocal_rank_fusion
from test_retrieval import search
from test_wiki import wiki, create_page
from test_sources import sources, upload, execute
from test_access import access
from test_spaces import spaces
from test_structured_search import structured
from test_annotations import annotations

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='isolated PostgreSQL required')


def ingest(source, body, **options):
    version = upload(source, data=body.encode(), **options)
    execute(source, 'source.extract', version['id'])
    return str(version['source_id'])


def test_hand_computable_document_scores_and_alias_dedup(search):
    service, wiki, source = search
    apple = ingest(source, 'apples apples pears')
    ingest(source, 'pears')
    result = service.search(wiki[1], 'apples', kind='source')
    hit, = result['hits']
    assert hit['resource_id'] == apple
    expected = math.log(1 + (2 - 1 + .5) / (1 + .5)) * (2 * 2.2) / (2 + 1.2 * (.25 + .75 * 3 / 2))
    assert hit['score'] == pytest.approx(expected)
    assert result['lexical_strategy'] == 'bm25'
    assert result['lexical_ranker_version'] == RANKER_VERSION
    assert service.search(wiki[1], 'apples apple apples', kind='source')['hits'] == result['hits']


@pytest.mark.parametrize('body,query', [
    ('BCL-2 expression inhibits apoptosis', 'Bcl2'),
    ('BCL-2 expression inhibits apoptosis', 'BCL'),
    ('Approximately 30 subjects', '30'),
    ('Tetraspanin-3 expression', 'Tetraspanin 3'),
    ('Tetraspanin 3 expression', 'Tetraspanin-3'),
    ('Studies demonstrate cellular responses', 'study response'),
    ('Configurazioni dei dispositivi aggiornati', 'configurazione dispositivo aggiornato'),
    ('東京 中文', '東京'),
])
def test_literal_stem_and_ordered_identifier_variants(search, body, query):
    service, wiki, source = search
    key = ingest(source, body)
    assert service.search(wiki[1], query, kind='source')['hits'][0]['resource_id'] == key


def test_identifier_numbers_remain_distinct_and_stop_only_is_empty(search):
    service, wiki, source = search
    ingest(source, 'BCL-2 Tetraspanin-3 protocol 1.2')
    for query in ('BCL3', 'Tetraspanin 4', '1.3', 'the and il gli'):
        assert service.search(wiki[1], query)['hits'] == []
    assert service.search(wiki[1], 'BCL-2')['hits'] == service.search(wiki[1], 'Bcl2')['hits']
    with service.database.engine.connect() as c:
        assert set(query_groups(c, 'BCL-2')[0]) & set(query_groups(c, 'Bcl2')[0]) == {'bcl2'}
        assert query_groups(c, 'Tetraspanin 3') != query_groups(c, '3 Tetraspanin')


def test_broad_matching_even_with_strict_hit_and_refuting_evidence(search):
    service, wiki, source = search
    exact = ingest(source, 'Treatment reduces mortality')
    refuting = ingest(source, 'Treatment does not reduce mortality')
    weak = ingest(source, 'Unrelated treatment overview')
    hits = service.search(wiki[1], 'Treatment reduces mortality', kind='source')['hits']
    assert {h['resource_id'] for h in hits} == {exact, refuting, weak}
    assert {h['resource_id'] for h in service.search(wiki[1], '"Treatment reduces mortality"', kind='source')['hits']} == {exact}
    assert service.search(wiki[1], 'mortality -treatment', kind='source')['hits'] == []


def test_complete_document_cross_chunk_counts_and_evidence_are_not_fabricated(search):
    service, wiki, source = search
    body = 'apoptosis ' + 'filler ' * 1800 + 'tetraspanin3'
    key = ingest(source, body)
    hits = service.search(wiki[1], 'apoptosis tetraspanin3', kind='source')['hits']
    hit, = hits
    assert hit['resource_id'] == key
    citation = hit['citation']
    assert body[citation['start_offset']:citation['end_offset']] == citation['body']
    with service.database.engine.connect() as c:
        length = c.execute(text('SELECT length FROM c0_lexical_documents')).scalar_one()
        counts = dict(c.execute(text('SELECT term,frequency FROM c0_lexical_terms')).all())
    assert length == 1802 and counts['filler'] == 1800


def test_stable_document_ties_and_source_pagination(search):
    service, wiki, source = search
    for n in range(4):
        ingest(source, 'identical evidence', title='Document '+str(n), metadata={'n':n})
    hits = service.search(wiki[1], 'evidence', kind='source')['hits']
    assert len(hits) == 4
    assert [h['citation']['document_id'] for h in hits] == sorted(h['citation']['document_id'] for h in hits)
    pages = [source[0].search(source[1], 'evidence', limit=1, offset=i) for i in range(5)]
    assert [str(p[0]['chunk_id']) for p in pages[:4]] == [h['id'] for h in hits]
    assert pages[4] == []


def test_title_only_wiki_edit_reindexes_and_retirement_cascades(search):
    service, wiki, source = search
    page = create_page(wiki, title='Glycoprotein', body='Original unchanged body')
    first = service.search(wiki[1], 'glycoprotein')['hits'][0]
    changed = wiki[0].update_page(wiki[1], page['id'], 'Tetraspanin', page['content']['body'], expected_revision=1, idempotency_key=uuid4().hex)
    second = service.search(wiki[1], 'tetraspanin')['hits'][0]
    assert first['id'] == second['id'] and first['content_hash'] == second['content_hash']
    assert service.search(wiki[1], 'glycoprotein')['hits'] == []
    wiki[0].update_page(wiki[1], page['id'], 'Current', 'Replacement body', expected_revision=2, idempotency_key=uuid4().hex)
    with service.database.engine.connect() as c:
        assert c.execute(text('SELECT count(*) FROM c0_lexical_terms WHERE document_id=:id'), {'id':first['id']}).scalar_one() == 0
    assert service.search(wiki[1], 'tetraspanin')['hits'] == []


def test_interrupted_index_write_rolls_back_with_content(search):
    service, wiki, source = search
    key = ingest(source, 'Published original')
    with service.database.engine.connect() as c:
        before = c.execute(text('SELECT document_id,term,frequency FROM c0_lexical_terms ORDER BY term')).all()
    with pytest.raises(RuntimeError):
        with service.database.engine.begin() as c:
            c.execute(text("UPDATE c0_documents SET body='Interrupted candidate'"))
            raise RuntimeError('interrupt publication')
    with service.database.engine.connect() as c:
        assert c.execute(text('SELECT document_id,term,frequency FROM c0_lexical_terms ORDER BY term')).all() == before
    assert service.search(wiki[1], 'published')['hits'][0]['resource_id'] == key
    assert service.search(wiki[1], 'interrupted')['hits'] == []


def test_hybrid_fuses_documents_once_and_keeps_actual_lexical_evidence():
    lexical = {'kind':'chunk','id':'lexical-chunk','resource_id':'source'}
    semantic = {'kind':'chunk','id':'different-chunk','resource_id':'source'}
    other = {'kind':'chunk','id':'other-chunk','resource_id':'other'}
    result = reciprocal_rank_fusion([lexical], [semantic, semantic, other], document_level=True)
    assert result[0]['id'] == 'lexical-chunk' and result[0]['score'] == pytest.approx(2/61)
    assert result[1]['score'] == pytest.approx(1/62)
    assert len(reciprocal_rank_fusion([lexical], [semantic])) == 2


def test_other_space_content_cannot_change_scores(spaces, search):
    from czero_core.identity import PermissionDenied, Role
    from test_spaces import create, member
    service, wiki, source = search
    reader = member(spaces, Role.READER)
    ingest(source, 'backup backup restore')
    ingest(source, 'restore')
    before = service.search(reader, 'backup restore', kind='source')
    private = create(spaces)
    private_source = (source[0].in_space(private['id']), *source[1:])
    ingest(private_source, 'backup ' * 500 + 'restore')
    assert service.search(reader, 'backup restore', kind='source') == before
    with pytest.raises(PermissionDenied):
        service.in_space(private['id']).search(reader, 'backup restore')
    grant = spaces[0].set_grant(spaces[1], private['id'], reader.user_id, Role.READER,
                              expected_revision=0, idempotency_key=uuid4().hex)
    assert service.in_space(private['id']).search(reader, 'backup')['hits']
    spaces[0].set_grant(spaces[1], private['id'], reader.user_id, None,
                       expected_revision=grant['revision'], idempotency_key=uuid4().hex)
    with pytest.raises(PermissionDenied):
        service.in_space(private['id']).search(reader, 'backup')


def test_filtered_out_documents_do_not_change_corpus_statistics(structured):
    from czero_core.structured import StructuredFilters
    from test_structured_search import annotate
    from test_annotations import wiki_target
    service, fixture, annotations = structured
    _, wiki, source = fixture
    page = create_page(wiki, title='Retention', body='backup backup restore')
    annotate(annotations, wiki[1], wiki_target(page), version_tags=['8'])
    filters = StructuredFilters(categories=['wiki'], version_tags=['8'])
    before = service.search(wiki[1], 'backup restore', filters=filters, mode='text')
    excluded = create_page(wiki, title='Retention', body='backup ' * 100)
    annotate(annotations, wiki[1], wiki_target(excluded), version_tags=['7'])
    ingest(source, 'backup ' * 500)
    assert service.search(wiki[1], 'backup restore', filters=filters, mode='text') == before


def test_retained_generations_backfill_without_replacing_citation_ids(tmp_path, predecessor_python):
    from alembic import command
    from alembic.config import Config
    from pathlib import Path
    import time
    import czero_core.migrate
    from sqlalchemy import create_engine
    from sqlalchemy.engine import make_url
    from czero_core.database import Database
    from czero_core.access import AccessService
    from czero_core.identity import VerifiedIdentity
    from czero_core.migrate import migrate_database
    from czero_core.retrieval import SearchService
    from czero_core.wiki import WikiService
    from czero_core.sources import OriginalStore, SourceService, register_source_handlers
    from czero_core.jobs import default_registry
    parsed = make_url(os.environ['CZERO_TEST_DATABASE_URL'])
    admin = create_engine(parsed, hide_parameters=True)
    name = 'c0_bm25_migration_' + uuid4().hex
    database = None
    try:
        with admin.connect().execution_options(isolation_level='AUTOCOMMIT') as c:
            c.execute(text('CREATE DATABASE '+name))
        database = Database(parsed.set(database=name).render_as_string(hide_password=False))
        config = Config()
        config.set_main_option('script_location', str(Path(czero_core.migrate.__file__).with_name('migrations')))
        with database.engine.begin() as c:
            config.attributes['connection'] = c
            command.upgrade(config, '0035_compilation_assessment')
        key = uuid4()
        issuer = 'https://migration.example.test'
        acl = AccessService(database, issuer, key)
        actor = acl.resolve(VerifiedIdentity(issuer, 'owner', str(key), 'owner', 'Owner', time.time()+300))
        with historical_space_authorization(predecessor_python) as PreviousSpaces:
            wiki = WikiService(database, acl)
            page = wiki.create_page(actor, 'retained', 'Tetraspanin', 'Original retained evidence', idempotency_key='page')
            registry = default_registry()
            originals = OriginalStore(tmp_path/'originals')
            register_source_handlers(registry, database, originals)
            source = SourceService(database, acl, registry, originals)
            fixture = (source, actor, registry, [])
            ingest(fixture, 'BCL-2 original retained evidence')
            def content(c):
                return {table:c.execute(text('SELECT row_to_json(t)::text FROM '+table+' t ORDER BY id')).scalars().all()
                        for table in ('c0_documents','c0_chunks','c0_source_versions','c0_wiki_revisions')}
            with database.engine.connect() as c:
                before = content(c)
        migrate_database(database)
        migrate_database(database)
        with database.engine.connect() as c:
            assert content(c) == before
            assert c.execute(text('SELECT count(*) FROM c0_lexical_documents')).scalar_one() == 2
        result = SearchService(database, acl).search(actor, 'Bcl2 tetraspanin', mode='text')
        assert len(result['hits']) == 2
        database.engine.dispose()  # Reopen connections; derivatives are persistent.
        assert SearchService(database, acl).search(actor, 'Bcl2 tetraspanin', mode='text') == result
    finally:
        if database is not None:
            database.close()
        with admin.connect().execution_options(isolation_level='AUTOCOMMIT') as c:
            c.execute(text('DROP DATABASE '+name))
        admin.dispose()


def test_representative_chunk_uses_literal_identifier_variant(search):
    service, wiki, source = search
    ingest(source, 'filler ' * 600 + 'BCL-2 inhibits apoptosis ' + 'filler ' * 600)
    hit, = service.search(wiki[1], 'Bcl2', kind='source')['hits']
    assert 'BCL-2' in hit['citation']['body']


def test_oversized_document_token_does_not_prevent_publication(search):
    service, wiki, source = search
    key = ingest(source, 'a'*4000+'\nretrievable evidence')
    assert service.search(wiki[1], 'retrievable', kind='source')['hits'][0]['resource_id'] == key


def test_alias_groups_merge_transitively():
    from czero_core.bm25 import query_groups
    class Connection:
        def execute(self, *args):
            return [(['a', 'b'],), (['c', 'd'],), (['d', 'e'],), (['b', 'e'],)]
    assert query_groups(Connection(), 'synthetic') == [['a', 'b', 'c', 'd', 'e']]


def test_document_evidence_loading_is_batched_and_keeps_exact_citations(search):
    from sqlalchemy import event
    from uuid import UUID
    service, wiki, source = search
    for n in range(8):
        ingest(source, 'Batched evidence '+str(n), title='Document '+str(n))
    statements = []
    def capture(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement)
    event.listen(service.database.engine, 'before_cursor_execute', capture)
    try:
        hits = service.search(wiki[1], 'batched evidence', kind='source')['hits']
    finally:
        event.remove(service.database.engine, 'before_cursor_execute', capture)
    assert len(hits) == 8
    assert sum('c.id AS chunk_id' in sql for sql in statements) == 1
    assert sum('SELECT id,current_version_id FROM c0_sources' in sql for sql in statements) == 1
    for hit in hits:
        citation = source[0].citation(source[1], UUID(hit['id']))
        assert hit['citation'] == {key: str(value) if isinstance(value, UUID) else value
                                   for key, value in citation.items()}


@pytest.mark.parametrize('kind', ['source', 'wiki'])
def test_batched_final_check_rejects_replacement_during_scoring(search, kind):
    from czero_core.current_content import ContentSuperseded
    service, wiki, source = search
    if kind == 'source':
        key = ingest(source, 'original evidence')
        def replace():
            ingest(source, 'replacement evidence', source_id=key, expected_revision=1)
    else:
        page = create_page(wiki, body='original evidence')
        def replace():
            wiki[0].update_page(wiki[1], page['id'], 'Replacement', 'replacement evidence',
                               expected_revision=1, idempotency_key=uuid4().hex)
    class Scorer:
        def score(self, query, candidates):
            replace()
            return {'usage': {}, 'truncated_candidates': 0,
                    'scores': {candidate['id']: 1.0 for candidate in candidates}}
    service.scorer = Scorer()
    service.scorer_mode = 'rerank'
    with pytest.raises(ContentSuperseded):
        service.search(wiki[1], 'original evidence', kind=kind, rerank='rerank')
