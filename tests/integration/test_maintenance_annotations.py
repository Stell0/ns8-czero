# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Maintenance metadata describes retained observations without rewriting them."""
import os
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4

import pytest

from czero_core.annotations import ContentTarget, annotation_value
from czero_core.knowledge import EvidenceNotReady
from czero_core.wiki import KnowledgeNotFound
from test_access import access
from test_annotations import annotations, wiki_target, write
from test_knowledge import knowledge, evidence, claim
from test_objects import objects
from test_sources import sources, upload, execute
from test_spaces import spaces, create
from test_wiki import wiki, create_page, create_entity

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='isolated PostgreSQL required')


def target_value(target):
    return {'kind':target.kind, 'id':str(target.id), 'revision':target.revision}


def source_ref(chunk):
    return {'kind':'chunk','id':str(chunk['id'])}


def test_explicit_supersession_keeps_prior_content_verification_and_evidence(knowledge, annotations):
    _, fixture, source_fixture = knowledge
    owner = fixture[1]
    old = create_page(fixture, body='Original interpretation')
    old_target = wiki_target(old)
    verified = write(annotations, owner, old_target, 'verification', {'status':'verified','confidence':0.8})
    version, document, chunk = evidence(knowledge)
    replacement = create_page(fixture, body='Revised interpretation; contradiction retained')
    value = {'knowledge_type':'procedure', 'status':'applicable', 'products':['C0'], 'components':['backup'],
        'version_tags':['0.43','0.430'], 'observed_at':'2026-10-18T11:00:00+02:00', 'confidence':None,
        'supersedes':[target_value(old_target)], 'source_references':[source_ref(chunk)],
        'extensions':{'future-maintenance-state':{'interpretation':'unknown'}}}
    result = write(annotations, owner, wiki_target(replacement), 'applicability', value, key='supersession')
    assert result['value']['knowledge_type'] == 'procedure'
    assert result['value']['supersedes'] == [target_value(old_target)]
    assert result['value']['source_references'] == [source_ref(chunk)]
    assert result['value']['confidence'] is None
    assert result['value']['observed_at'] == '2026-10-18T09:00:00+00:00'
    assert fixture[0].get_page(owner, old['id']) == old
    assert annotations.get(owner, old_target, 'verification') == verified
    assert annotations.get(owner, wiki_target(replacement), 'verification')['status'] == 'unknown'
    write(annotations, owner, wiki_target(replacement), 'applicability', {'status':'contradicted','knowledge_type':'future-vendor-kind'}, 1)
    assert annotations.history(owner, wiki_target(replacement), 'applicability')['revisions'][1]['value'] == result['value']
    assert write(annotations, owner, wiki_target(replacement), 'applicability', value, key='supersession') == result
    assert source_fixture[0].document(owner, version['id']) == document
    assert source_fixture[0].citation(owner, chunk['id'])['source_hash'] == version['content_hash']


def test_ready_source_references_are_required_independently_of_verification_status(sources, annotations, wiki):
    version = upload(sources)
    execute(sources, 'source.extract', version['id'])
    document = sources[0].document(wiki[1], version['id'])
    chunk = sources[0].chunks(wiki[1], document['id'])[0]
    target = wiki_target(create_page(wiki))
    # A real existing chunk whose parent became unready is still unsuitable.
    from sqlalchemy import text
    with annotations.database.engine.begin() as connection:
        connection.execute(text("UPDATE c0_source_versions SET state='failed' WHERE id=:id"), {'id':version['id']})
    for namespace in ('applicability','verification'):
        with pytest.raises(EvidenceNotReady):
            write(annotations, wiki[1], target, namespace, {'status':'unverified','source_references':[source_ref(chunk)]})
        assert annotations.get(wiki[1], target, namespace)['revision'] == 0
    with annotations.database.engine.begin() as connection:
        connection.execute(text("UPDATE c0_source_versions SET state='ready' WHERE id=:id"), {'id':version['id']})
    result = write(annotations, wiki[1], target, 'verification', {'status':'unverified','source_references':[source_ref(chunk)]})
    assert result['value']['source_references'] == [source_ref(chunk)]


def test_cross_space_supersession_and_source_references_are_not_resolved(spaces, knowledge, annotations):
    _, fixture, _ = knowledge
    private = create(spaces)
    target = wiki_target(create_page(fixture))
    hidden = fixture[0].in_space(private['id']).create_page(fixture[1], 'hidden-'+uuid4().hex,
        'Hidden', 'Hidden content', idempotency_key=uuid4().hex)
    fixture[2].append(hidden['id'])
    with pytest.raises(KnowledgeNotFound):
        write(annotations, fixture[1], target, 'applicability', {'supersedes':[target_value(wiki_target(hidden))]})
    _, _, shared_chunk = evidence(knowledge)
    selected = annotations.in_space(private['id'])
    with pytest.raises(KnowledgeNotFound):
        write(selected, fixture[1], wiki_target(hidden), 'verification', {'source_references':[source_ref(shared_chunk)]})
    assert annotations.get(fixture[1], target, 'applicability')['revision'] == 0
    assert selected.get(fixture[1], wiki_target(hidden), 'verification')['revision'] == 0


def test_maintenance_metadata_never_changes_strict_record_payload_or_claim_assertion(knowledge, annotations, objects):
    service, fixture, _ = knowledge
    owner = fixture[1]
    record = objects[0].create(owner, objects[2], {'name':'strict'})
    entity = create_entity(fixture)
    _, _, chunk = evidence(knowledge)
    assertion = claim(knowledge, entity, 'Linux', chunk)
    for target in (ContentTarget('object',record['id'],1),ContentTarget('entity',entity['id'],1),ContentTarget('claim',assertion['id'],1)):
        result = write(annotations, owner, target, 'applicability', {'knowledge_type':'vendor-future-type','source_references':[source_ref(chunk)]})
        assert result['value']['knowledge_type'] == 'vendor-future-type'
    assert objects[0].get(owner, record['id']) == record
    assert service.get_claim(owner, assertion['id'])['value'] == assertion['value']


def test_superseded_unannotated_record_retains_observed_identity_after_removal(annotations, wiki, objects):
    old = objects[0].create(wiki[1], objects[2], {'name':'superseded'})
    target = ContentTarget('object', old['id'], 1)
    page = create_page(wiki)
    stored = write(annotations, wiki[1], wiki_target(page), 'applicability', {'supersedes':[target_value(target)]})
    observed = annotations.get(wiki[1], target, 'verification')
    objects[0].delete(wiki[1], old['id'], expected_revision=1)
    retained = annotations.get(wiki[1], target, 'verification')
    assert retained['target'] == observed['target']
    assert retained['revision'] == 0 and retained['status'] == 'unknown' and retained['target_archived']
    assert annotations.get(wiki[1], wiki_target(page), 'applicability') == stored


def test_self_supersession_is_rejected_without_an_annotation(annotations, wiki):
    target = wiki_target(create_page(wiki))
    with pytest.raises(ValueError, match='invalid_self_supersession'):
        write(annotations, wiki[1], target, 'applicability', {'supersedes':[target_value(target)]})
    assert annotations.get(wiki[1], target, 'applicability')['revision'] == 0


def test_object_supersession_and_object_batch_have_a_consistent_lock_order(annotations, wiki, objects):
    from sqlalchemy import event, text
    from czero_core.wiki import KnowledgeConflict
    owner = wiki[1]
    rows = sorted([objects[0].create(owner,objects[2],{'name':'first'}),
                   objects[0].create(owner,objects[2],{'name':'second'})], key=lambda row:str(row['id']))
    first_locked, second_shared, resume = Event(), Event(), Event()
    def pause(connection,cursor,statement,parameters,context,executemany):
        if 'SELECT * FROM c0_objects' not in statement:
            return
        identifier = str(parameters.get('id'))
        if 'FOR UPDATE' in statement and identifier==str(rows[0]['id']):
            first_locked.set()
            assert resume.wait(timeout=10)
        elif 'FOR SHARE' in statement and identifier==str(rows[1]['id']):
            second_shared.set()
            assert resume.wait(timeout=10)
    operations=[{'operation':'update','id':str(row['id']),'data':{'name':'updated-'+str(index)},'expected_revision':1}
                for index,row in enumerate(rows)]
    def annotate():
        try:
            return write(annotations,owner,ContentTarget('object',rows[1]['id'],1),'applicability',
                {'supersedes':[{'kind':'object','id':str(rows[0]['id']),'revision':1}]})
        except KnowledgeConflict:
            return 'stale'
    event.listen(annotations.database.engine,'after_cursor_execute',pause)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            batch=pool.submit(objects[0].batch,owner,operations)
            annotation=None
            try:
                assert first_locked.wait(timeout=10)
                annotation=pool.submit(annotate)
                deadline=time.monotonic()+5
                while not second_shared.is_set():
                    with annotations.database.engine.connect() as connection:
                        waiting=connection.execute(text('''SELECT count(*) FROM pg_locks WHERE locktype='advisory'
                            AND objid=49375 AND NOT granted AND database=(SELECT oid FROM pg_database WHERE datname=current_database())''')).scalar_one()
                    if waiting:
                        break
                    assert time.monotonic()<deadline,'Annotation neither serialized nor reached its content lock'
                    time.sleep(.02)
            finally:
                resume.set()
            assert len(batch.result(timeout=10))==2
            assert annotation.result(timeout=10)=='stale'
    finally:
        event.remove(annotations.database.engine,'after_cursor_execute',pause)
    assert all(objects[0].get(owner,row['id'])['revision']==2 for row in rows)


@pytest.mark.parametrize('value', [
    {'knowledge_type':''}, {'knowledge_type':True}, {'knowledge_type':'x'*65},
    {'supersedes':[{'kind':'page','id':str(uuid4()),'revision':1}]},
    {'supersedes':[{'kind':'entity','id':str(uuid4()),'revision':True}]},
    {'supersedes':[{'kind':'entity','id':str(uuid4()),'revision':1,'space_id':str(uuid4())}]},
    {'source_references':[{'kind':'object','id':str(uuid4())}]},
    {'source_references':[{'kind':'chunk','id':'invalid'}]},
    {'source_references':[{'kind':'chunk','id':str(uuid4())}]*33}])
def test_maintenance_fields_are_typed_and_bounded(value):
    with pytest.raises(ValueError):
        annotation_value('applicability', value)
