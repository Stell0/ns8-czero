# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
import hashlib,json,shutil
from pathlib import Path
from types import SimpleNamespace
import pytest
from c0_ingest.errors import C0Error
from c0_projects.cli import run
from c0_projects.legacy import validate_snapshot

FIXTURES=Path(__file__).resolve().parents[2]/'fixtures/wikiplant'


@pytest.mark.parametrize('name',['robotelier','myprojects'])
def test_raw_layout_preserves_ids_provenance_pending_work_and_clean_markdown(tmp_path,name):
    source=FIXTURES/name;before={path.relative_to(source).as_posix():hashlib.sha256(path.read_bytes()).hexdigest() for path in source.rglob('*') if path.is_file()}
    first=validate_snapshot(source,tmp_path/'first');second=validate_snapshot(source,tmp_path/'second')
    assert first['status']==second['status']=='VALIDATED' and first['manifest_hash']==second['manifest_hash']
    manifest=json.loads(Path(first['manifest_path']).read_text());mappings=manifest['mappings']
    assert manifest['target_project_id'] is None and manifest['target_space_id'] is None and manifest['activation_required']
    assert all(row['c0_id'] is None and row['c0_version_id'] is None for row in mappings)
    assert all(row['provenance']['source_generation']=='fixture-generation-1' for row in mappings)
    wiki=next(row for row in mappings if row['kind']=='wiki')
    assert (tmp_path/'first'/wiki['body_path']).read_text().lstrip().startswith('# ')
    assert not (tmp_path/'first'/wiki['body_path']).read_text().startswith('---json')
    child=next(row for row in mappings if row['kind']=='queue' and row['legacy_id']=='queue-child')
    metadata=json.loads((tmp_path/'first'/child['metadata_path']).read_text())
    assert metadata['parent_ids']==['queue-root'] and metadata['status']=='retry_wait' and metadata['attempts']==1
    assert any(row['kind']=='claim' and row['legacy_id']=='claim-1' for row in mappings)
    state=next(row for row in mappings if row['kind']=='state')
    assert json.loads((tmp_path/'first'/state['metadata_path']).read_text())['operation_receipts'][0]['status']=='ACCEPTED_PENDING_MERGE'
    assert before=={path.relative_to(source).as_posix():hashlib.sha256(path.read_bytes()).hexdigest() for path in source.rglob('*') if path.is_file()}
    args=SimpleNamespace(group='wikiplant',operation='validate',input=source,output=tmp_path/'cli',apply=False,max_records=10000,max_bytes=100*1024*1024)
    result,code=run(args,client_factory=lambda *_:pytest.fail('Offline parser must not authenticate or contact C0'))
    assert code==0 and result['writes_c0']==0 and not result['migration_performed']


def test_serialized_wiki_object_is_a_blocked_repair_proposal_not_a_markdown_body(tmp_path):
    source=tmp_path/'raw';shutil.copytree(FIXTURES/'robotelier',source)
    page=source/'data/wiki/concepts/wiki-1.md';page.write_text(json.dumps({'id':'bad-page','title':'Envelope','body':'# Recovered Markdown\n\nSynthetic prose.'}))
    result=validate_snapshot(source,tmp_path/'proposal');manifest=json.loads(Path(result['manifest_path']).read_text())
    assert result['status']=='BLOCKED' and 'serialized_wiki_envelope' in {row['code'] for row in manifest['validation']['findings']}
    wiki=next(row for row in manifest['mappings'] if row['kind']=='wiki')
    assert (tmp_path/'proposal'/wiki['body_path']).read_text().startswith('# Recovered Markdown')
    assert json.loads(page.read_text())['body'].startswith('# Recovered Markdown')


def test_canonical_metadata_disagreement_and_checksum_tampering_are_visible(tmp_path):
    source=tmp_path/'raw';shutil.copytree(FIXTURES/'robotelier',source)
    registry=source/'data/TOPICS.md';registry.write_text(registry.read_text().replace('### Humanoid robots','### Unrecorded changed scope',1))
    result=validate_snapshot(source,tmp_path/'review');manifest=json.loads(Path(result['manifest_path']).read_text())
    codes={row['code'] for row in manifest['validation']['findings']}
    assert result['status']=='BLOCKED' and {'invalid_export_manifest','invalid_topic_registry'}<=codes


def test_snapshot_symlinks_and_outputs_inside_source_are_rejected(tmp_path):
    source=tmp_path/'raw';shutil.copytree(FIXTURES/'myprojects',source)
    with pytest.raises(C0Error):validate_snapshot(source,source/'output')
    other=tmp_path/'other';other.mkdir()
    with pytest.raises(C0Error):validate_snapshot(source,other/'..'/'raw'/'hidden-output')
    assert not (source/'hidden-output').exists()
    (source/'data/escape').symlink_to(tmp_path/'secret')
    with pytest.raises(C0Error):validate_snapshot(source,tmp_path/'blocked')


def test_actual_recoverable_archive_generations_remain_distinct(tmp_path):
    source=tmp_path/'raw';shutil.copytree(FIXTURES/'robotelier',source)
    original=source/'data/wiki/concepts/wiki-1.md';archived=source/'data/archive/wiki-1/revision-1.md'
    archived.parent.mkdir(parents=True);archived.write_bytes(original.read_bytes())
    manifest_path=source/'export-manifest.json';manifest=json.loads(manifest_path.read_text())
    old=next(row for row in manifest['files'] if row['path']=='data/wiki/concepts/wiki-1.md')
    manifest['files'].append({**old,'path':'data/archive/wiki-1/revision-1.md','source_generation':'fixture-generation-0'})
    manifest_path.write_text(json.dumps(manifest))
    result=validate_snapshot(source,tmp_path/'history');prepared=json.loads(Path(result['manifest_path']).read_text())
    versions=[row for row in prepared['mappings'] if row['kind']=='wiki' and row['legacy_id']=='wiki-1']
    assert result['status']=='VALIDATED' and {row['legacy_version'] for row in versions}=={'fixture-generation-0','fixture-generation-1'}


@pytest.mark.parametrize('field,bad',[('parent_ids','{}'),('created_at','2026-01-01T10:00:00'),('expansion_priority','0')])
def test_invalid_queue_reference_timestamp_or_reset_depth_blocks_preparation(tmp_path,field,bad):
    import csv,io
    source=tmp_path/'raw';shutil.copytree(FIXTURES/'myprojects',source)
    path=source/'data/research_queue.csv';reader=csv.DictReader(io.StringIO(path.read_text()));rows=list(reader)
    rows[1][field]=bad;stream=io.StringIO();writer=csv.DictWriter(stream,reader.fieldnames);writer.writeheader();writer.writerows(rows);path.write_text(stream.getvalue())
    result=validate_snapshot(source,tmp_path/'review');manifest=json.loads(Path(result['manifest_path']).read_text())
    assert result['status']=='BLOCKED'
    assert {'invalid_csv','lineage_depth_reset'}.intersection(row['code'] for row in manifest['validation']['findings'])


@pytest.mark.parametrize('field,bad',[('start_date','2027-02-30'),('recurrence','{"frequency":"hourly"}'),('updated_at','2026-01-01')])
def test_invalid_calendar_dates_or_unbounded_recurrence_block_preparation(tmp_path,field,bad):
    import csv,io
    source=tmp_path/'raw';shutil.copytree(FIXTURES/'robotelier',source)
    path=source/'data/calendar.csv';reader=csv.DictReader(io.StringIO(path.read_text()));rows=list(reader)
    rows[0][field]=bad;stream=io.StringIO();writer=csv.DictWriter(stream,reader.fieldnames);writer.writeheader();writer.writerows(rows);path.write_text(stream.getvalue())
    result=validate_snapshot(source,tmp_path/'review');manifest=json.loads(Path(result['manifest_path']).read_text())
    assert result['status']=='BLOCKED' and any(row['code']=='invalid_csv' for row in manifest['validation']['findings'])


def test_offline_github_storage_binding_and_config_history_are_preserved(tmp_path):
    import yaml
    source=tmp_path/'raw';shutil.copytree(FIXTURES/'myprojects',source)
    instance_path=source/'INSTANCE.json';instance=json.loads(instance_path.read_text())
    for key in ('root_folder_id','config_file_id','drive_map_file_id'):instance.pop(key)
    instance.update(schema_version=2,storage={'provider':'github','repository_id':'170001',
        'repository':'fixture-c0-lab/synthetic-storage','canonical_ref':'refs/heads/main','first_verified_commit':'c'*40})
    instance_path.write_text(json.dumps(instance))
    config_path=source/'config.yml';config=yaml.safe_load(config_path.read_text());config['storage']={
        key:value for key,value in instance['storage'].items() if key!='first_verified_commit'}
    config['storage'].update(root_prefix='',consistency_mode='git-fast-forward',limits={'max_file_bytes':512000,
        'max_transaction_bytes':8000000,'max_repository_bytes':500000000,'max_paths_per_transaction':200})
    config_path.write_text(yaml.safe_dump(config,sort_keys=False))
    export_path=source/'export-manifest.json';export=json.loads(export_path.read_text())
    for entry in export['files']:
        raw=(source/entry['path']).read_bytes();entry.update(size=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    export_path.write_text(json.dumps(export))
    result=validate_snapshot(source,tmp_path/'prepared');manifest=json.loads(Path(result['manifest_path']).read_text())
    assert result['status']=='VALIDATED' and manifest['storage_provenance']==instance['storage']
    assert manifest['configuration']['runtime']==config['runtime'] and manifest['target_space_id'] is None
