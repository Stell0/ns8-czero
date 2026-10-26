# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Protected research projects using existing typed storage and transaction receipts."""
from datetime import datetime, timezone
import hashlib
import json

from sqlalchemy import text

from .identity import PermissionDenied, Role
from .objects import ObjectService, ObjectConflict, ObjectNotFound, page
from .object_schema import bounded_json, validate_record
from .project_schema import PREFIX, SCHEMAS, normalize_manifest, identifier, next_occurrence, project_unique_fields
from .receipts import mutate, snapshot
from .spaces import SpaceBound
from .project_workflows import ProjectWorkflows
from .project_monitoring import ProjectMonitoring
from .project_schedules import ProjectSchedules
from .project_evidence import ProjectEvidence
from .project_reports import ProjectReports


class ProjectConflict(ObjectConflict):
    pass


class ProjectNotFound(ObjectNotFound):
    pass


def logical_key(kind, identity):
    return hashlib.sha256((kind + '\n' + identity).encode()).hexdigest()


class ProjectService(ProjectReports, ProjectEvidence, ProjectSchedules, ProjectMonitoring, ProjectWorkflows, SpaceBound):
    conflict = ProjectConflict
    def __init__(self, database, access, *, clock=None):
        self.database, self.access = database, access
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def _authorize(self, connection, actor, role=Role.READER):
        if self._space_id is None:
            raise ValueError('explicit_project_space_required')
        current = self._space_authorize(connection, actor, role)
        if connection.execute(text('SELECT shared FROM c0_spaces WHERE id=:space'),
                              {'space': self._space_id}).scalar_one():
            raise PermissionDenied()
        return current

    def _admin(self, connection, actor, role=Role.ADMIN):
        return self._authorize(connection, actor, Role.ADMIN)

    def _objects(self):
        # This flag is trusted Python wiring, never a request field.
        return ObjectService(self.database, self.access, managed_projects=True).in_space(self._space_id)

    def _bootstrap(self, connection, actor, kinds=None):
        for kind in SCHEMAS if kinds is None else kinds:
            schema = SCHEMAS[kind]
            fields=project_unique_fields(kind)
            type_name = PREFIX + kind
            row = connection.execute(text('SELECT schema,unique_fields FROM c0_object_types WHERE name=:name'),
                                     {'name': type_name}).mappings().one_or_none()
            if row is not None:
                if row['schema'] != schema or row['unique_fields'] != fields:
                    raise ProjectConflict()
                continue
            self._admin(connection, actor)
            connection.execute(text('''INSERT INTO c0_object_types(name,label,schema,unique_fields)
                VALUES(:name,:label,CAST(:schema AS jsonb),CAST(:fields AS text[]))'''),
                {'name': type_name, 'label': 'Research project ' + kind, 'schema': json.dumps(schema),'fields':fields})

    def _find(self, connection, kind, identity, *, required=True):
        row = connection.execute(text('''SELECT o.* FROM c0_object_keys k JOIN c0_objects o ON o.id=k.object_id AND o.space_id=k.space_id
            WHERE k.space_id=:space AND k.type_name=:type AND k.field='key' AND k.value=CAST(:key AS jsonb)'''),
            {'space': self._space_id, 'type': PREFIX + kind, 'key': json.dumps(logical_key(kind, identity))}).mappings().one_or_none()
        if row is None and required:
            raise ProjectNotFound()
        return dict(row) if row else None

    def _save(self, connection, actor, kind, identity, data, *, previous=None):
        values = {'key': logical_key(kind, identity), **data}
        if previous is None:
            operation = {'operation': 'create', 'type_name': PREFIX + kind, 'data': values}
        else:
            operation = {'operation': 'update', 'id': str(previous['id']),
                'expected_revision': previous['revision'], 'data': values}
        return self._objects()._write(connection, actor, operation)

    def _mutate(self, actor, operation, data, key, execute, *, admin=False, lease=None):
        bounded_json(data, maximum=262144)
        def source_binding(connection):
            if operation not in ('source_status','connector_status','source_snapshot'):return
            connector_id=data.get('connector_id') or data['data']['connector_id']
            binding=self._find(connection,'connector_lease_v1',connector_id,required=False)
            if binding and (lease is None or lease.get('run_id')!=binding['data']['run_id']):raise ProjectConflict()
        if lease is not None:
            if admin:raise ValueError('admin_operation_has_no_workflow_lease')
            return self._workflow_mutate(actor,operation,data,key,lease,
                lambda connection,current,run:execute(connection,current),guard=source_binding)
        def authorize(connection,captured,minimum):
            current=(self._admin if admin else self._authorize)(connection,captured,minimum)
            source_binding(connection)
            return current
        return mutate(self.database,authorize,actor,'project.'+operation,data,key,
            execute,conflict=ProjectConflict,lock_objects=True)

    def _manifest(self, connection):
        return self._find(connection, 'manifest_v1', 'manifest')

    def get(self, actor):
        with self.database.engine.connect() as connection:
            self._authorize(connection, actor)
            return snapshot(self._manifest(connection))

    def list_records(self, actor, kind, *, limit=50, offset=0, descending=False):
        if kind not in SCHEMAS:
            raise ValueError('invalid_project_record_kind')
        page(limit, offset)
        if type(descending) is not bool:raise ValueError('invalid_project_record_order')
        order='DESC' if descending else 'ASC'
        with self.database.engine.connect() as connection:
            self._authorize(connection, actor)
            rows = connection.execute(text('''SELECT * FROM c0_objects
                WHERE space_id=:space AND type_name=:type ORDER BY created_at '''+order+',id '+order+' LIMIT :limit OFFSET :offset'),
                {'space': self._space_id, 'type': PREFIX + kind, 'limit': limit, 'offset': offset}).mappings()
            return snapshot([dict(row) for row in rows])

    def _primary_topics(self, connection, manifest):
        for topic_id in manifest['primary_topic_ids']:
            topic = self._find(connection, 'topic_v1', topic_id)['data']
            if topic['classification'] != 'user' or topic['lifecycle'] != 'active' or not topic['authorized_by']:
                raise ValueError('primary_topic_requires_active_user_authorization')

    def initialize(self, actor, manifest, *, authorization_ref, idempotency_key):
        manifest = normalize_manifest(manifest)
        if manifest['space_id'] != str(self._space_id):
            raise ValueError('project_space_mismatch')
        if not isinstance(authorization_ref, str) or not 1 <= len(authorization_ref) <= 512:
            raise ValueError('project_authorization_reference_required')
        def execute(connection, current):
            self._bootstrap(connection, current)
            if self._find(connection, 'manifest_v1', 'manifest', required=False):
                raise ProjectConflict()
            self._primary_topics(connection, manifest)
            result = self._save(connection, current, 'manifest_v1', 'manifest', {'version': 1, 'manifest': manifest})
            self._save(connection, current, 'config_v1', '1', {'version': 1, 'manifest': manifest,
                'actor_id': str(current.user_id), 'authorization_ref': authorization_ref,
                'recorded_at': self.clock().isoformat()})
            return result
        return self._mutate(actor, 'initialize', {'manifest': manifest, 'authorization_ref': authorization_ref},
                            idempotency_key, execute, admin=True)

    def configure(self, actor, manifest, *, expected_revision, authorization_ref, idempotency_key):
        manifest = normalize_manifest(manifest)
        if manifest['space_id'] != str(self._space_id):
            raise ValueError('project_space_mismatch')
        if type(expected_revision) is not int or expected_revision < 1:
            raise ValueError('invalid_revision')
        if not isinstance(authorization_ref, str) or not 1 <= len(authorization_ref) <= 512:
            raise ValueError('project_authorization_reference_required')
        def execute(connection, current):
            self._bootstrap(connection,current)
            previous = self._manifest(connection)
            if previous['revision'] != expected_revision:
                raise ProjectConflict()
            old = previous['data']['manifest']
            if manifest['project_id'] != old['project_id']:
                raise ProjectConflict()
            self._primary_topics(connection, manifest)
            version = previous['data']['version'] + 1
            self._save(connection, current, 'config_v1', str(version), {'version': version, 'manifest': manifest,
                'actor_id': str(current.user_id), 'authorization_ref': authorization_ref,
                'recorded_at': self.clock().isoformat()})
            return self._save(connection, current, 'manifest_v1', 'manifest', {'version': version, 'manifest': manifest}, previous=previous)
        return self._mutate(actor, 'configure', {'manifest': manifest, 'expected_revision': expected_revision,
            'authorization_ref': authorization_ref}, idempotency_key, execute, admin=True)

    def set_topic(self, actor, topic, *, expected_revision=0, idempotency_key):
        topic = bounded_json(topic)
        allowed = set(SCHEMAS['topic_v1']['properties']) - {'key', 'schema_version', 'authorized_by', 'created_at', 'expires_at'}
        if set(topic) - allowed:
            raise ValueError('invalid_project_topic')
        identifier(topic.get('topic_id'))
        if type(expected_revision) is not int or expected_revision < 0:
            raise ValueError('invalid_revision')
        def execute(connection, current):
            self._bootstrap(connection, current, ('manifest_v1', 'config_v1', 'topic_v1'))
            previous = self._find(connection, 'topic_v1', topic['topic_id'], required=False)
            if (previous['revision'] if previous else 0) != expected_revision:
                raise ProjectConflict()
            values = {'schema_version': 1, 'aliases': [], 'parent_ids': [], 'anchor_ids': [],
                'originating_question': '', 'direct_contribution': '', 'assessment_ref': '', 'authorization_ref': '',
                'authorized_by': '', 'lifecycle': 'active', **topic,
                'created_at': previous['data']['created_at'] if previous else self.clock().isoformat(), 'expires_at': ''}
            kind = values['classification']
            manifest_row = self._find(connection, 'manifest_v1', 'manifest', required=False)
            if (manifest_row and values['topic_id'] in manifest_row['data']['manifest']['primary_topic_ids']
                    and (kind != 'user' or values['lifecycle'] != 'active')):
                raise ValueError('primary_topic_requires_active_user_authorization')
            if kind == 'user' or (previous and previous['data']['classification'] == 'user'):
                current = self._admin(connection, actor)
                if not values['authorization_ref'].strip():
                    raise ValueError('project_authorization_reference_required')
                values['authorized_by'] = str(current.user_id)
                if kind == 'user':
                    values['anchor_ids'] = [values['topic_id']]
            elif previous and previous['data']['authorized_by']:
                values['authorized_by'] = previous['data']['authorized_by']
            if previous and previous['data']['lifecycle'] in ('archived', 'retired') and values['lifecycle'] not in ('archived','retired'):
                raise ValueError('archived_topic_requires_new_explicit_authorization')
            if len(set(values['parent_ids'])) != len(values['parent_ids']) or values['topic_id'] in values['parent_ids']:
                raise ValueError('invalid_topic_parents')
            for parent_id in values['parent_ids']:
                parent = self._find(connection, 'topic_v1', parent_id)['data']
                if parent['classification'] == 'peripheral':
                    raise ValueError('peripheral_topic_is_terminal')
                ancestors = connection.execute(text('''WITH RECURSIVE ancestors AS (
                    SELECT data FROM c0_objects WHERE space_id=:space AND type_name=:type AND data->>'topic_id'=:parent
                    UNION SELECT o.data FROM c0_objects o JOIN ancestors a
                    ON a.data->'parent_ids' ? (o.data->>'topic_id')
                    WHERE o.space_id=:space AND o.type_name=:type)
                    SELECT data->>'topic_id' FROM ancestors LIMIT 1001'''),
                    {'space': self._space_id, 'type': PREFIX + 'topic_v1', 'parent': parent_id}).scalars().all()
                if len(ancestors) > 1000 or values['topic_id'] in ancestors:
                    raise ValueError('invalid_topic_ancestry')
            if kind in ('adjacent', 'peripheral'):
                if not values['anchor_ids'] or len(set(values['anchor_ids'])) != len(values['anchor_ids']):
                    raise ValueError('topic_requires_direct_user_anchor')
                for anchor_id in values['anchor_ids']:
                    anchor = self._find(connection, 'topic_v1', anchor_id)['data']
                    if anchor['classification'] != 'user' or anchor['lifecycle'] != 'active':
                        raise ValueError('topic_requires_direct_user_anchor')
                if not values['direct_contribution'].strip() or not values['assessment_ref'].strip():
                    raise ValueError('topic_requires_recorded_assessment')
            if kind == 'peripheral':
                manifest = self._manifest(connection)['data']['manifest']
                values['expires_at'] = (previous['data']['expires_at'] if previous and previous['data']['expires_at']
                    else next_occurrence(manifest, 'weekly', self.clock()).isoformat())
            values = validate_record(SCHEMAS['topic_v1'], {'key': logical_key('topic_v1', topic['topic_id']), **values})
            return self._save(connection, current, 'topic_v1', topic['topic_id'], {k: v for k, v in values.items() if k != 'key'}, previous=previous)
        # Initial schema bootstrap is Admin-only. Thereafter Editors can assess adjacent topics.
        with self.database.engine.connect() as connection:
            self._authorize(connection, actor, Role.EDITOR)
            bootstrapped = connection.execute(text('SELECT 1 FROM c0_object_types WHERE name=:name'),
                {'name': PREFIX + 'topic_v1'}).scalar_one_or_none()
        return self._mutate(actor, 'topic', {'topic': topic, 'expected_revision': expected_revision}, idempotency_key,
            execute, admin=not bootstrapped)

    def set_connector(self, actor, definition, *, expected_revision=0, authorization_ref, idempotency_key):
        definition = validate_record(SCHEMAS['connector_v1']['properties']['definition'], definition)
        identifier(definition['id'])
        adapter=definition['adapter']
        if adapter in ('http','rss_atom','sitemap'):
            from urllib.parse import urlsplit, parse_qsl
            import re
            parsed=urlsplit(definition.get('url',''))
            if (parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password or parsed.fragment
                    or parsed.port not in (None,443 if parsed.scheme=='https' else 80)
                    or any(ord(c)<=32 for c in definition['url'])
                    or any(re.sub('[^a-z0-9]','',k.lower()).endswith(('token','key','secret','password','signature','credential','assertion','sessionid')) or k.lower() in {'auth','authorization','code','jwt','session','sig'} for k,_ in parse_qsl(parsed.query))):
                raise ValueError('invalid_source_url')
        if adapter in ('local_files','wikiplant_export') and not definition.get('root'):
            raise ValueError('explicit_local_root_required')
        if adapter=='github':
            import re
            if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9_][A-Za-z0-9_.-]{0,99}',definition.get('repository','')):
                raise ValueError('invalid_github_repository')
        from pathlib import PurePosixPath
        for path in definition.get('paths',[]):
            if PurePosixPath(path).is_absolute() or '..' in PurePosixPath(path).parts or '\\' in path:
                raise ValueError('unsafe_local_selection')
        selections={'github':{'readme','docs','commits','releases','issues','pull_requests','comments'},'c0_space':{'wiki','sources'}}
        if adapter in selections and set(definition['include'])-selections[adapter]:
            raise ValueError('invalid_source_selection')
        if type(expected_revision) is not int or expected_revision<0:
            raise ValueError('invalid_revision')
        if type(authorization_ref) is not str or not authorization_ref.strip() or len(authorization_ref)>512:
            raise ValueError('project_authorization_reference_required')
        def execute(connection,current):
            self._bootstrap(connection,current)
            self._manifest(connection)
            if definition['adapter']=='c0_space':
                source = definition.get('source_space_id')
                if not source or source == str(self._space_id) or not definition.get('authorization_ref'):
                    raise ValueError('explicit_source_space_authorization_required')
                from .spaces import SpaceService
                SpaceService(self.database,self.access).authorize(connection,current,space_id=source)
            previous=self._find(connection,'connector_v1',definition['id'],required=False)
            if (previous['revision'] if previous else 0)!=expected_revision:
                raise ProjectConflict()
            fingerprint=hashlib.sha256(json.dumps(definition,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
            values = {
                'connector_id':definition['id'],'definition':definition,'definition_hash':fingerprint,
                'authorization_ref':authorization_ref,'approved_by':str(current.user_id)}
            version = previous['revision']+1 if previous else 1
            self._save(connection,current,'connector_config_v1',definition['id']+':'+str(version),{**values,'version':version})
            return self._save(connection,current,'connector_v1',definition['id'],values,previous=previous)
        return self._mutate(actor,'connector',{'definition':definition,'expected_revision':expected_revision,
            'authorization_ref':authorization_ref},idempotency_key,execute,admin=True)

    def source_status(self, actor, connector_id, external_id):
        identifier(connector_id);identifier(external_id)
        with self.database.engine.connect() as connection:
            self._authorize(connection,actor)
            return snapshot(self._find(connection,'source_sync_v1',connector_id+':'+external_id))

    def save_source_status(self, actor, data, *, expected_revision=0, lease=None, idempotency_key):
        data=bounded_json(data)
        if 'key' in data:
            raise ValueError('invalid_source_status')
        validate_record(SCHEMAS['source_sync_v1'], {'key':'validated', **data})
        from uuid import UUID
        from .project_schema import timestamp
        UUID(data['source_id']); UUID(data['version_id'])
        if type(expected_revision) is not int or expected_revision<0:
            raise ValueError('invalid_revision')
        for field in ('last_content_hash', 'parent_content_hash'):
            if len(data[field])!=64 or any(ch not in '0123456789abcdef' for ch in data[field]):
                raise ValueError('invalid_source_hash')
        for field in ('retrieved_at','published_at','updated_at'):
            if data['provenance'][field]: timestamp(data['provenance'][field])
        if data['retry_after']: timestamp(data['retry_after'])
        bounded_json(json.loads(data['provenance']['details']),maximum=8192)
        if data['remote_cursor']:
            bounded_json(json.loads(data['remote_cursor']), maximum=4096)
        def execute(connection,current):
            connector=self._find(connection,'connector_v1',data['connector_id'])
            manifest=self._manifest(connection)['data']['manifest']
            if data['definition_hash']!=connector['data']['definition_hash']:
                raise ProjectConflict()
            if data['connector_id'] not in manifest['connector_ids'] or not connector['data']['definition']['enabled']:
                raise ValueError('source_connector_not_enabled')
            values=validate_record(SCHEMAS['source_sync_v1'],{'key':logical_key('source_sync_v1',data['connector_id']+':'+data['external_id']),**data})
            row=connection.execute(text('''SELECT source_id,content_hash,state FROM c0_source_versions
                WHERE space_id=:space AND id=CAST(:id AS uuid)'''),{'space':self._space_id,'id':values['version_id']}).mappings().one_or_none()
            if row is None or str(row['source_id'])!=values['source_id'] or row['content_hash']!=values['last_content_hash']:
                raise ValueError('source_version_identity_mismatch')
            if values['sync_status']=='verified' and row['state']!='ready':
                raise ValueError('source_extraction_not_verified')
            values['extraction_status']=row['state']
            if values['end_byte']<values['start_byte']:
                raise ValueError('invalid_source_part_offsets')
            previous=self._find(connection,'source_sync_v1',values['connector_id']+':'+values['external_id'],required=False)
            if (previous['revision'] if previous else 0)!=expected_revision:
                raise ProjectConflict()
            values['last_attempt_at']=self.clock().isoformat()
            values['last_success_at']=(self.clock().isoformat() if values['sync_status']=='verified'
                else previous['data']['last_success_at'] if previous else '')
            history_key=values['connector_id']+':'+values['external_id']+':'+values['version_id']
            if values['sync_status']=='verified' and not self._find(connection,'source_sync_history_v1',history_key,required=False):
                self._save(connection,current,'source_sync_history_v1',history_key,{k:v for k,v in values.items() if k!='key'})
            return self._save(connection,current,'source_sync_v1',values['connector_id']+':'+values['external_id'],
                {k:v for k,v in values.items() if k!='key'},previous=previous)
        return self._mutate(actor,'source_status',{'data':data,'expected_revision':expected_revision},idempotency_key,execute,lease=lease)

    def save_connector_status(self, actor, data, *, verified_receipt_ids=None, expected_revision=0, lease=None, idempotency_key):
        data=bounded_json(data)
        from uuid import UUID
        verified_receipt_ids=[] if verified_receipt_ids is None else verified_receipt_ids
        if (type(verified_receipt_ids) is not list or len(verified_receipt_ids)>1000
                or len(set(verified_receipt_ids))!=len(verified_receipt_ids)):
            raise ValueError('invalid_source_receipt_proof')
        for value in verified_receipt_ids:
            if type(value) is not str:raise ValueError('invalid_source_receipt_proof')
            UUID(value)
        if 'key' in data or type(expected_revision) is not int or expected_revision<0:
            raise ValueError('invalid_connector_status')
        values=validate_record(SCHEMAS['connector_sync_v1'],{'key':'validated',**data})
        if values['remote_cursor']: bounded_json(json.loads(values['remote_cursor']),maximum=4096)
        if values['progress_cursor']: bounded_json(json.loads(values['progress_cursor']),maximum=4096)
        if values['verified_items']!=len(verified_receipt_ids) or values['verified_items']>values['discovered_items']:
            raise ValueError('invalid_connector_counters')
        if values['status']=='complete' and (values['verified_items']!=values['discovered_items'] or values['last_error']):
            raise ValueError('incomplete_connector_coverage')
        def execute(connection,current):
            connector=self._find(connection,'connector_v1',values['connector_id'])['data']
            if connector['definition_hash']!=values['definition_hash']:
                raise ProjectConflict()
            if not connector['definition']['enabled'] or values['connector_id'] not in self._manifest(connection)['data']['manifest']['connector_ids']:
                raise ValueError('source_connector_not_enabled')
            if verified_receipt_ids:
                verified=connection.execute(text('''SELECT count(DISTINCT o.id) FROM c0_objects o
                    JOIN c0_source_versions v ON v.id=CAST(o.data->>'version_id' AS uuid) AND v.space_id=o.space_id
                    JOIN c0_sources s ON s.id=v.source_id AND s.space_id=v.space_id AND NOT s.deleted
                    JOIN c0_objects h ON h.space_id=o.space_id AND h.type_name=:history
                      AND h.data @> jsonb_build_object('connector_id',CAST(:connector AS text),'external_id',o.data->>'external_id','version_id',o.data->>'version_id')
                    JOIN c0_objects p ON p.space_id=o.space_id AND p.type_name=:snapshot
                      AND p.data @> jsonb_build_object('connector_id',CAST(:connector AS text),'external_id',o.data->>'parent_external_id','content_hash',o.data->>'parent_content_hash')
                      AND (p.data->'part_receipt_ids') ? CAST(h.id AS text)
                    WHERE o.space_id=:space AND o.type_name=:type AND o.id=ANY(CAST(:ids AS uuid[]))
                      AND o.data->>'connector_id'=:connector AND o.data->>'definition_hash'=:hash
                      AND o.data->>'sync_status'='verified' AND v.state='ready'
                      AND v.content_hash=o.data->>'last_content_hash' AND CAST(v.source_id AS text)=o.data->>'source_id'
                    '''),{'space':self._space_id,'type':PREFIX+'source_sync_v1','ids':verified_receipt_ids,
                        'history':PREFIX+'source_sync_history_v1','snapshot':PREFIX+'source_snapshot_v1',
                        'connector':values['connector_id'],'hash':values['definition_hash']}).scalar_one()
                if verified!=len(verified_receipt_ids):raise ValueError('unverified_connector_publication')
            previous=self._find(connection,'connector_sync_v1',values['connector_id'],required=False)
            if (previous['revision'] if previous else 0)!=expected_revision:
                raise ProjectConflict()
            matching=previous if previous and previous['data']['definition_hash']==values['definition_hash'] else None
            from datetime import timedelta
            from .project_schema import timestamp
            failures=0 if values['status']=='complete' else min(10,(matching['data']['attempt_count'] if matching else 0)+1)
            retry=values['retry_after']
            if failures:
                fallback=self.clock()+timedelta(seconds=min(3600,30*2**(failures-1)))
                requested=timestamp(retry) if retry else fallback
                retry=min(max(requested,fallback),self.clock()+timedelta(days=1)).isoformat()
            saved={**values,'last_attempt_at':self.clock().isoformat(),'attempt_count':failures,'retry_after':retry if failures else '',
                'last_success_at':self.clock().isoformat() if values['status']=='complete' else matching['data']['last_success_at'] if matching else '',
                'progress_cursor':values['progress_cursor'] if values['verified_items']==values['discovered_items'] else matching['data']['progress_cursor'] if matching else '',
                'remote_cursor':values['remote_cursor'] if values['status']=='complete' else matching['data']['remote_cursor'] if matching else ''}
            return self._save(connection,current,'connector_sync_v1',values['connector_id'],{k:v for k,v in saved.items() if k!='key'},previous=previous)
        return self._mutate(actor,'connector_status',{'data':data,'verified_receipt_ids':verified_receipt_ids,'expected_revision':expected_revision},idempotency_key,execute,lease=lease)

    def save_source_snapshot(self, actor, connector_id, external_id, content_hash, part_receipt_ids, *, expected_revision=0, lease=None, idempotency_key):
        identifier(connector_id)
        if type(external_id) is not str or not 1<=len(external_id)<=4096:
            raise ValueError('invalid_external_identity')
        from uuid import UUID
        if type(part_receipt_ids) is not list or not 1<=len(part_receipt_ids)<=100 or len(set(part_receipt_ids))!=len(part_receipt_ids):
            raise ValueError('invalid_source_parts')
        for value in part_receipt_ids:UUID(value)
        if type(expected_revision) is not int or expected_revision<0:raise ValueError('invalid_revision')
        payload={'connector_id':connector_id,'external_id':external_id,'content_hash':content_hash,
            'part_receipt_ids':part_receipt_ids,'expected_revision':expected_revision}
        def execute(connection,current):
            connector=self._find(connection,'connector_v1',connector_id)
            if connector_id not in self._manifest(connection)['data']['manifest']['connector_ids'] or not connector['data']['definition']['enabled']:
                raise ValueError('source_connector_not_enabled')
            total=0;digest=hashlib.sha256();binary=False;immutable=[]
            for number,receipt_id in enumerate(part_receipt_ids,1):
                row=connection.execute(text('''SELECT o.data,v.media_type,d.body FROM c0_objects o
                    JOIN c0_source_versions v ON v.id=CAST(o.data->>'version_id' AS uuid) AND v.space_id=o.space_id
                    JOIN c0_documents d ON d.version_id=v.id AND d.space_id=v.space_id
                    WHERE o.space_id=:space AND o.type_name=:type AND o.id=CAST(:id AS uuid) AND v.state='ready' '''),
                    {'space':self._space_id,'type':PREFIX+'source_sync_v1','id':receipt_id}).mappings().one_or_none()
                if row is None:raise ValueError('unverified_source_part')
                data=row['data']
                if (data['connector_id']!=connector_id or data['parent_external_id']!=external_id
                        or data['parent_content_hash']!=content_hash or data['part_number']!=number
                        or data['start_byte']!=total or data['sync_status']!='verified'
                        or data['definition_hash']!=connector['data']['definition_hash']):
                    raise ValueError('source_part_identity_mismatch')
                if row['media_type'] in ('text/plain','text/markdown'):
                    content=row['body'].encode()
                    if hashlib.sha256(content).hexdigest()!=data['last_content_hash'] or len(content)!=data['end_byte']-total:
                        raise ValueError('source_part_content_mismatch')
                    digest.update(content)
                else:
                    binary=True
                    if len(part_receipt_ids)!=1 or content_hash!=data['last_content_hash']:
                        raise ValueError('invalid_binary_source_parts')
                historical=self._find(connection,'source_sync_history_v1',connector_id+':'+data['external_id']+':'+data['version_id'])
                immutable.append(str(historical['id']))
                total=data['end_byte']
                if total>16777216:raise ValueError('source_snapshot_too_large')
            if not binary and digest.hexdigest()!=content_hash:raise ValueError('source_snapshot_hash_mismatch')
            identity=connector_id+':'+external_id
            previous=self._find(connection,'source_snapshot_v1',identity,required=False)
            if (previous['revision'] if previous else 0)!=expected_revision:raise ProjectConflict()
            values={'connector_id':connector_id,'external_id':external_id,'content_hash':content_hash,
                'part_receipt_ids':immutable,'total_bytes':total,'verified_at':self.clock().isoformat()}
            historical=identity+':'+content_hash
            if not self._find(connection,'source_snapshot_history_v1',historical,required=False):
                self._save(connection,current,'source_snapshot_history_v1',historical,values)
            return self._save(connection,current,'source_snapshot_v1',identity,values,previous=previous)
        return self._mutate(actor,'source_snapshot',payload,idempotency_key,execute,lease=lease)
