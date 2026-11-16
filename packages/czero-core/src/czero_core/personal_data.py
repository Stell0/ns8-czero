# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Directory-bound spaces and fenced imports. Native collectors are trusted callers.

No remote I/O, credentials or source bodies are persisted in synchronization state.
Remote inventories never confer authority. All publication uses SourceService staging.
"""
import hashlib
from io import BytesIO
import json
import re
from uuid import UUID, uuid4

from sqlalchemy import text

from .identity import PermissionDenied, Role
from .spaces import SPACE_LOCK, hold_authority, require_scope, space_uuid
from .sources import _label, _metadata
from .extraction import MEDIA_TYPES, MAX_UPLOAD
from .receipts import snapshot


class PersonalDataConflict(ValueError):
    def __init__(self):
        super().__init__('personal_data_changed')


def can_edit_personal(c, issuer, directory_id):
    # Predecessor compatibility: access operations also run during recovery tests.
    if not c.execute(text("SELECT to_regclass('c0_personal_owners') IS NOT NULL")).scalar_one():
        return False
    return c.execute(text('''SELECT EXISTS(SELECT 1 FROM c0_personal_owners o
        JOIN c0_personal_config p ON p.issuer=o.issuer AND p.provider_id=o.provider_id
        WHERE o.issuer=:issuer AND o.directory_id=:key AND o.active)'''),
        {'issuer': issuer, 'key': directory_id}).scalar_one()


def require_consent_role(actor, role):
    # Eligibility only. Every actual content operation still selects/rechecks a space.
    if role is Role.EDITOR and actor.personal_editor:
        return
    actor.require(role)


def _locks(c):
    for key in (49372, 49379, SPACE_LOCK, 49382):
        c.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': key})


def _services(value):
    if type(value) is not dict or set(value) - {'nethvoice', 'webtop'}:
        raise ValueError('invalid_personal_services')
    return {key: str(space_uuid(item)) for key, item in value.items()}


class PersonalDataService:
    def __init__(self, database, access, sources=None):
        self.database, self.access, self.sources = database, access, sources

    def fence_native(self, *, disabled=False, services=None):
        """Stop publication before NS8 changes services/authentication; no remote I/O."""
        if type(disabled) is not bool:raise ValueError('invalid_personal_config')
        if services is not None:services=_services(services)
        with self.database.engine.begin() as c:
            _locks(c)
            if not c.execute(text("SELECT to_regclass('c0_personal_config') IS NOT NULL")).scalar_one():
                return {'status':'unverified','pending_cleanup':0}
            c.execute(text("""UPDATE c0_personal_config SET validated=false,generation=generation+1,
                enabled=CASE WHEN :disabled THEN false ELSE enabled END WHERE issuer=:issuer"""),
                {'issuer':self.access.issuer,'disabled':disabled})
            if disabled:
                c.execute(text("""UPDATE c0_personal_imports i SET state='cleanup' FROM c0_personal_owners o
                    WHERE i.owner_id=o.id AND o.issuer=:issuer AND i.state NOT IN ('excluded','removed')"""),{'issuer':self.access.issuer})
            if services is not None:
                c.execute(text("""UPDATE c0_personal_imports i SET state='cleanup' FROM c0_personal_owners o
                    WHERE i.owner_id=o.id AND o.issuer=:issuer AND i.state NOT IN ('excluded','removed')
                    AND CAST(:services AS jsonb)->>i.connector IS DISTINCT FROM i.instance_id::text"""),
                    {'issuer':self.access.issuer,'services':json.dumps(services)})
            count=c.execute(text("""SELECT count(*) FROM c0_personal_imports i JOIN c0_personal_owners o ON o.id=i.owner_id
                WHERE o.issuer=:issuer AND i.state='cleanup'"""),{'issuer':self.access.issuer}).scalar_one()
            return {'status':'unverified','pending_cleanup':count}

    def configure(self, actor, *, provider_id, enabled, services, expected_generation):
        return self._configure(actor, provider_id=provider_id, enabled=enabled, services=services,
                               expected_generation=expected_generation)

    def configure_native(self, *, provider_id, enabled, services, expected_generation):
        """Trusted in-process NS8 lifecycle entry; never registered as a user operation."""
        return self._configure(None, provider_id=provider_id, enabled=enabled, services=services,
                               expected_generation=expected_generation)

    def _configure(self, actor, *, provider_id, enabled, services, expected_generation):
        provider = space_uuid(provider_id)
        services = _services(services)
        if type(enabled) is not bool or (enabled and not services) or type(expected_generation) is not int or expected_generation < 0:
            raise ValueError('invalid_personal_config')
        with self.database.engine.begin() as c:
            _locks(c)
            if actor is not None:
                current = self.access.checked_actor(c, actor)
                current.require(Role.ADMIN)
                require_scope(current, Role.ADMIN)
            old = c.execute(text('SELECT * FROM c0_personal_config WHERE issuer=:issuer FOR UPDATE'),
                            {'issuer': self.access.issuer}).mappings().one_or_none()
            if (old['generation'] if old else 0) != expected_generation:
                raise PersonalDataConflict()
            if old and old['provider_id'] != provider:
                # A changed provider must never silently inherit an old directory UUID.
                raise ValueError('personal_provider_change_requires_disconnect')
            if old and old['enabled'] == enabled and old['services'] == services:
                return snapshot(dict(old))
            if old:
                c.execute(text('''UPDATE c0_personal_imports i SET state='cleanup'
                    FROM c0_personal_owners o WHERE i.owner_id=o.id AND o.issuer=:issuer
                    AND i.state NOT IN ('excluded','removed') AND
                    (NOT :enabled OR CAST(:services AS jsonb)->>i.connector IS DISTINCT FROM i.instance_id::text)'''),
                    {'issuer': self.access.issuer, 'enabled': enabled, 'services': json.dumps(services)})
            row = c.execute(text('''INSERT INTO c0_personal_config(issuer,provider_id,enabled,services)
                VALUES (:issuer,:provider,:enabled,CAST(:services AS jsonb)) ON CONFLICT(issuer)
                DO UPDATE SET enabled=EXCLUDED.enabled,services=EXCLUDED.services,
                generation=c0_personal_config.generation+1,validated=false RETURNING *'''),
                {'issuer': self.access.issuer, 'provider': provider, 'enabled': enabled,
                 'services': json.dumps(services)}).mappings().one()
            return snapshot(dict(row))

    def reconcile_directory(self, *, provider_id, entries, complete=False):
        """Trusted native directory read; incomplete snapshots never disable absentees.

        entries are normalized immutable IDs, usernames and explicit active flags,
        after the adapter has excluded service/machine entries and ambiguous mappings.
        No login identity or application membership is created here.
        """
        provider = space_uuid(provider_id)
        if type(entries) is not list or len(entries) > 1000 or type(complete) is not bool:
            raise ValueError('invalid_directory_inventory')
        normalized = []
        for entry in entries:
            if type(entry) is not dict or set(entry) != {'directory_id', 'username', 'active'} or type(entry['active']) is not bool:
                raise ValueError('invalid_directory_entry')
            normalized.append((space_uuid(entry['directory_id']), _label(entry['username'], 128), entry['active']))
        if len({row[0] for row in normalized}) != len(normalized) or len({row[1].casefold() for row in normalized}) != len(normalized):
            raise ValueError('ambiguous_directory_inventory')
        with self.database.engine.begin() as c:
            _locks(c)
            config = c.execute(text('SELECT * FROM c0_personal_config WHERE issuer=:issuer FOR UPDATE'),
                               {'issuer': self.access.issuer}).mappings().one()
            if config['provider_id'] != provider:
                raise PersonalDataConflict()
            for directory, username, active in normalized:
                values = dict(issuer=self.access.issuer, provider=provider, directory=directory, username=username, active=active, alias=username.casefold())
                old = c.execute(text('''SELECT * FROM c0_personal_owners
                    WHERE provider_id=:provider AND directory_id=:directory'''), values).mappings().one_or_none()
                if old is not None and old['issuer']!=self.access.issuer:
                    raise PersonalDataConflict()
                ambiguous=c.execute(text('''SELECT EXISTS(SELECT 1 FROM c0_personal_owners
                    WHERE provider_id=:provider AND directory_id<>:directory AND :alias=ANY(usernames))'''),values).scalar_one()
                values['ambiguous']=ambiguous
                if old is None:
                    if not active:
                        continue
                    space = uuid4()
                    c.execute(text("INSERT INTO c0_spaces(id,name,personal) VALUES (:space,'Personal Data',true)"), {'space': space})
                    c.execute(text('''INSERT INTO c0_personal_owners(id,issuer,provider_id,directory_id,username,active,space_id,usernames,source_identity_ambiguous)
                        VALUES (:id,:issuer,:provider,:directory,:username,:active,:space,ARRAY[:alias],:ambiguous)'''), {**values, 'id': uuid4(), 'space': space})
                else:
                    c.execute(text('''UPDATE c0_personal_owners SET username=:username,active=:active,
                        usernames=CASE WHEN :alias=ANY(usernames) THEN usernames ELSE array_append(usernames,:alias) END,
                        source_identity_ambiguous=source_identity_ambiguous OR :ambiguous WHERE id=:id'''), {**values, 'id': old['id']})
                    if old['active'] and not active:
                        self._revoke(c, directory)
            if complete:
                lost = c.execute(text('''UPDATE c0_personal_owners SET active=false
                    WHERE issuer=:issuer AND provider_id=:provider AND active
                    AND NOT (directory_id=ANY(CAST(:ids AS uuid[]))) RETURNING directory_id'''),
                    {'issuer': self.access.issuer, 'provider': provider, 'ids': [row[0] for row in normalized]}).scalars().all()
                for directory in lost:
                    self._revoke(c, directory)
            c.execute(text('''UPDATE c0_personal_imports i SET state='cleanup' FROM c0_personal_owners o
                WHERE i.owner_id=o.id AND o.issuer=:issuer AND NOT o.active AND i.state NOT IN ('excluded','removed')'''),
                {'issuer': self.access.issuer})
            return snapshot([dict(row) for row in c.execute(text('''SELECT id,space_id,directory_id,username,active,source_identity_ambiguous
                FROM c0_personal_owners WHERE issuer=:issuer AND provider_id=:provider ORDER BY directory_id'''),
                {'issuer': self.access.issuer, 'provider': provider}).mappings()])

    def _revoke(self, c, directory):
        from .api_keys import revoke_account_keys
        account = c.execute(text('SELECT id FROM c0_accounts WHERE issuer=:issuer AND account_key=:key'),
                            {'issuer': self.access.issuer, 'key': directory}).scalar_one_or_none()
        if account:
            revoke_account_keys(c, account)
            c.execute(text('DELETE FROM c0_oauth_grants WHERE account_id=:id'), {'id': account})

    def validate_binding(self, *, generation, provider_id, services):
        """Called only after actual native provider/capability verification, no HTTP input."""
        with self.database.engine.begin() as c:
            _locks(c)
            row = c.execute(text('''UPDATE c0_personal_config SET validated=true
                WHERE issuer=:issuer AND provider_id=:provider AND generation=:generation
                AND services=CAST(:services AS jsonb) AND enabled RETURNING generation'''),
                {'issuer': self.access.issuer, 'provider': space_uuid(provider_id),
                 'generation': generation, 'services': json.dumps(_services(services))}).scalar_one_or_none()
            if row is None:
                raise PersonalDataConflict()

    def _fence(self, c, owner_id, generation, connector, instance_id):
        row = c.execute(text('''SELECT o.* FROM c0_personal_owners o
            JOIN c0_personal_config p ON p.issuer=o.issuer AND p.provider_id=o.provider_id
            WHERE o.id=:owner AND o.issuer=:issuer AND o.active AND NOT o.source_identity_ambiguous AND p.enabled AND p.validated
            AND p.generation=:generation AND p.services->>:connector=:instance
            AND NOT EXISTS (SELECT 1 FROM c0_accounts a JOIN c0_account_blocks b ON b.account_id=a.id
                WHERE a.issuer=o.issuer AND a.account_key=o.directory_id)'''),
            {'owner': owner_id, 'issuer': self.access.issuer, 'generation': generation,
             'connector': connector, 'instance': str(instance_id)}).mappings().one_or_none()
        if row is None:
            raise PersonalDataConflict()
        return row

    def submit(self, *, owner_id, generation, connector, instance_id, remote_key, kind,
               title, content, media_type='text/plain', scan_id=None, metadata=None):
        """Remote content is already read; the same transaction fences and stages it."""
        if connector not in ('nethvoice', 'webtop') or not isinstance(content, bytes) or not 0 < len(content) <= MAX_UPLOAD or media_type not in MEDIA_TYPES:
            raise ValueError('invalid_personal_document')
        owner_id, instance_id = space_uuid(owner_id), space_uuid(instance_id)
        remote_key, kind, title = _label(remote_key, 512), _label(kind, 32), _label(title, 256)
        digest = hashlib.sha256(content).hexdigest()
        slot=(metadata or {}).get('personal_import_slot')
        identity_kind=(metadata or {}).get('personal_identity_kind')
        if slot is not None:slot=_label(slot,512)
        if connector=='nethvoice':
            unique=_label((metadata or {}).get('uniqueid'),128)
            linked=(metadata or {}).get('linkedid') or ''
            if (not re.fullmatch(r'[A-Za-z0-9_.-]{1,128}',unique) or not isinstance(linked,str)
                    or len(linked)>128 or any(ord(c)<32 for c in linked)):
                raise ValueError('invalid_personal_identity')
            # Call lookup identity belongs to the receipt, never editable source metadata.
            slot=json.dumps([unique,linked],ensure_ascii=False,separators=(',',':'))
        if identity_kind not in (None,'message_id','content_hash'):raise ValueError('invalid_personal_identity')
        # Metadata is limited and validated by the existing source pipeline.
        encoded = _metadata({**(metadata or {}), 'personal_import': {'connector': connector, 'instance_id': str(instance_id),
            'owner_id': str(owner_id), 'remote_key': remote_key, 'kind': kind, 'configuration_generation': generation}})
        values = dict(owner=owner_id, connector=connector, instance=instance_id, remote=remote_key, kind=kind)
        from .current_content import content_lock
        with self.database.engine.begin() as c:
            content_lock(c)
            hold_authority(c)
            owner = self._fence(c, owner_id, generation, connector, instance_id)
            if connector=='webtop' and kind=='attachment':
                parent_key=_label((metadata or {}).get('parent_import_key'),512)
                parent=c.execute(text("""SELECT i.state,s.deleted FROM c0_personal_imports i
                    LEFT JOIN c0_sources s ON s.id=i.source_id WHERE i.owner_id=:owner AND i.connector=:connector
                    AND i.instance_id=:instance AND i.remote_key=:parent AND i.kind='message'"""),
                    {**values,'parent':parent_key}).mappings().one_or_none()
                if parent is None:raise ValueError('personal_attachment_parent_missing')
                if parent['state'] in ('excluded','cleanup','removed') or parent['deleted']:
                    return {'state':'excluded','source_id':None}
            previous = c.execute(text('''SELECT * FROM c0_personal_imports WHERE owner_id=:owner AND connector=:connector
                AND instance_id=:instance AND remote_key=:remote AND kind=:kind FOR UPDATE'''), values).mappings().one_or_none()
            if previous is None and slot is not None and c.execute(text('''SELECT 1 FROM c0_personal_imports
                WHERE owner_id=:owner AND connector=:connector AND instance_id=:instance AND slot_key=:slot
                AND state='excluded' AND identity_kind='content_hash' LIMIT 1'''),{**values,'slot':slot}).scalar_one_or_none():
                return {'state':'excluded','source_id':None}
            source = None
            if previous and previous['source_id'] and previous['state']!='removed':
                source = c.execute(text('SELECT * FROM c0_sources WHERE id=:id FOR UPDATE'), {'id': previous['source_id']}).mappings().one()
            state = previous['state'] if previous else 'managed'
            if source and source['deleted']:
                state = 'excluded'
            elif source and source['revision'] != previous['source_revision']:
                state = 'overridden'
            if state in ('excluded', 'overridden', 'cleanup'):
                c.execute(text('''UPDATE c0_personal_imports SET state=:state,last_seen_scan=:scan,slot_key=:slot
                    WHERE owner_id=:owner AND connector=:connector AND instance_id=:instance AND remote_key=:remote AND kind=:kind'''),
                    {**values, 'state': state, 'scan': scan_id,'slot':slot})
                return {'state': state, 'source_id': str(source['id']) if source else None}
            staging=c.execute(text("""SELECT v.state,v.media_type,v.publication_title,v.publication_metadata,j.state AS job_state FROM c0_source_versions v
                LEFT JOIN c0_jobs j ON j.id=v.job_id WHERE v.id=:id"""),
                {'id':previous['version_id']}).mappings().one_or_none() if previous else None
            refresh_staging=bool(staging and staging['state']=='queued' and
                (previous['generation']!=generation or staging['job_state']=='failed'))
            published=bool(source and previous and source['current_version_id']==previous['version_id'])
            same_publication=bool(source and staging and staging['media_type']==media_type
                and (source['title'] if published else staging['publication_title'])==title
                and (source['metadata'] if published else staging['publication_metadata'])==json.loads(encoded))
            if same_publication and previous and previous['content_hash'] == digest and state == 'managed' and previous['generation']==generation and not refresh_staging:
                c.execute(text('''UPDATE c0_personal_imports SET last_seen_scan=:scan,slot_key=:slot WHERE owner_id=:owner
                    AND connector=:connector AND instance_id=:instance AND remote_key=:remote AND kind=:kind'''), {**values, 'scan': scan_id,'slot':slot})
                return {'state': 'unchanged', 'source_id': str(previous['source_id'])}
            selected = self.sources.in_space(owner['space_id'])
            result = selected._ingest(c, BytesIO(content), title=title, filename='personal-data', media_type=media_type,
                retain_original=False, encoded=encoded, source_id=source['id'] if source else None,
                expected_revision=source['revision'] if source else None,force_reindex=refresh_staging)
            revision = c.execute(text('SELECT revision FROM c0_sources WHERE id=:id'), {'id': result['source_id']}).scalar_one()
            c.execute(text('''INSERT INTO c0_personal_imports(owner_id,connector,instance_id,remote_key,kind,source_id,source_revision,content_hash,last_seen_scan,generation,version_id,slot_key,identity_kind)
                VALUES (:owner,:connector,:instance,:remote,:kind,:source,:revision,:hash,:scan,:generation,:version,:slot,:identity_kind)
                ON CONFLICT(owner_id,connector,instance_id,remote_key,kind) DO UPDATE
                SET source_id=EXCLUDED.source_id,source_revision=EXCLUDED.source_revision,content_hash=EXCLUDED.content_hash,
                    state='managed',last_seen_scan=EXCLUDED.last_seen_scan,generation=EXCLUDED.generation,version_id=EXCLUDED.version_id,slot_key=EXCLUDED.slot_key,identity_kind=EXCLUDED.identity_kind'''),
                {**values, 'source': result['source_id'], 'revision': revision, 'hash': digest, 'scan': scan_id, 'generation': generation, 'version': result['id'], 'slot': slot, 'identity_kind': identity_kind})
            return {'state': 'staged', 'source_id': str(result['source_id']), 'version_id': str(result['id'])}

    def cleanup(self, *, limit=50):
        """Resumable content retirement, including overridden imports; no remote I/O."""
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError('invalid_limit')
        from .current_content import content_lock, retire_versions
        from .extraction_queue import cancel_versions
        with self.database.engine.begin() as c:
            content_lock(c)
            hold_authority(c)
            rows = c.execute(text('''SELECT i.* FROM c0_personal_imports i JOIN c0_personal_owners o ON o.id=i.owner_id
                WHERE o.issuer=:issuer AND (i.state='cleanup' OR (i.state='excluded' AND EXISTS(SELECT 1 FROM c0_source_versions v WHERE v.source_id=i.source_id))) ORDER BY i.owner_id,i.remote_key LIMIT :limit FOR UPDATE OF i'''),
                {'issuer': self.access.issuer, 'limit': limit}).mappings().all()
            for row in rows:
                if row['source_id']:
                    ids = c.execute(text('SELECT id FROM c0_source_versions WHERE source_id=:id'), {'id': row['source_id']}).scalars().all()
                    cancel_versions(c, ids, 'personal_import_removed')
                    c.execute(text('''UPDATE c0_sources SET deleted=true,current_version_id=NULL,revision=revision+1,
                        title='Removed personal import',metadata='{}'::jsonb WHERE id=:id'''), {'id': row['source_id']})
                    retire_versions(c, ids)
                c.execute(text('''UPDATE c0_personal_imports SET state=CASE WHEN state='excluded' THEN 'excluded' ELSE 'removed' END,content_hash=NULL,source_revision=NULL
                    WHERE owner_id=:owner AND connector=:connector AND instance_id=:instance AND remote_key=:remote AND kind=:kind'''),
                    dict(owner=row['owner_id'], connector=row['connector'], instance=row['instance_id'], remote=row['remote_key'], kind=row['kind']))
            return len(rows)


def guard_publication(c, source_id, version_id=None):
    """Extraction cannot publish a queued import after disable or local replacement."""
    if not c.execute(text("SELECT to_regclass('c0_personal_imports') IS NOT NULL")).scalar_one():
        return
    hold_authority(c)
    row = c.execute(text('''SELECT i.version_id,i.generation,i.state,i.source_revision,s.revision,
        o.active,o.source_identity_ambiguous,o.provider_id,p.provider_id AS configured_provider,p.enabled,p.validated,
        EXISTS(SELECT 1 FROM c0_accounts a JOIN c0_account_blocks b ON b.account_id=a.id
            WHERE a.issuer=o.issuer AND a.account_key=o.directory_id) AS blocked,
        p.generation AS current_generation,p.services->>i.connector AS selected_instance,i.instance_id
        FROM c0_personal_imports i JOIN c0_personal_owners o ON o.id=i.owner_id
        JOIN c0_personal_config p ON p.issuer=o.issuer JOIN c0_sources s ON s.id=i.source_id
        WHERE i.source_id=:id'''), {'id':source_id}).mappings().one_or_none()
    if row and version_id is not None and row['version_id']!=version_id:
        return
    if row and (row['source_identity_ambiguous'] or row['blocked'] or row['state']!='managed' or row['source_revision']!=row['revision'] or not row['active']
        or not row['enabled'] or not row['validated'] or row['provider_id']!=row['configured_provider']
        or row['generation']!=row['current_generation'] or row['selected_instance']!=str(row['instance_id'])):
        from .current_content import ContentSuperseded
        raise ContentSuperseded()


def record_checkpoint(service, *, owner_id, generation, connector, instance_id, cursor, status, error_code=None, complete=False):
    """Coverage observations contain only bounded cursors/counters, never source text."""
    allowed={'unverified','backfill','partial','suspended','degraded','reconciled'}
    errors={None,'source_unavailable','session_unavailable','capability_unverified','identity_ambiguous',
            'inventory_incomplete','source_not_found','too_large','credentials_missing','provider_mismatch','account_blocked'}
    if status not in allowed or error_code not in errors or type(complete) is not bool or type(cursor) is not dict:
        raise ValueError('invalid_personal_checkpoint')
    allowed_keys={'page_size','head_folder_index','page','folder_index','window_start','window_end','documents','skipped','scan_id','inventory_hash','folder_hash','scan_skipped','read_verified'}
    if set(cursor)-allowed_keys:
        raise ValueError('invalid_personal_cursor')
    encoded=json.dumps(cursor,sort_keys=True,allow_nan=False)
    if len(encoded.encode())>4096:
        raise ValueError('invalid_personal_cursor')
    with service.database.engine.begin() as c:
        hold_authority(c)
        # Status is allowed for a suspended session; never convert it into deletion.
        owner=c.execute(text('''SELECT o.id FROM c0_personal_owners o JOIN c0_personal_config p ON p.issuer=o.issuer
            WHERE o.id=:owner AND o.issuer=:issuer AND p.generation=:generation'''),
            {'owner':space_uuid(owner_id),'issuer':service.access.issuer,'generation':generation}).scalar_one_or_none()
        if owner is None:
            raise PersonalDataConflict()
        c.execute(text('''INSERT INTO c0_personal_checkpoints(owner_id,connector,instance_id,generation,cursor,status,error_code,last_success,last_inventory)
            VALUES (:owner,:connector,:instance,:generation,CAST(:cursor AS jsonb),:status,:error,
                CASE WHEN :success THEN now() END,CASE WHEN :complete THEN now() END)
            ON CONFLICT(owner_id,connector,instance_id) DO UPDATE SET generation=EXCLUDED.generation,cursor=EXCLUDED.cursor,
                status=EXCLUDED.status,error_code=EXCLUDED.error_code,
                last_success=COALESCE(EXCLUDED.last_success,c0_personal_checkpoints.last_success),
                last_inventory=COALESCE(EXCLUDED.last_inventory,c0_personal_checkpoints.last_inventory)'''),
            {'owner':owner,'connector':connector,'instance':space_uuid(instance_id),'generation':generation,
             'cursor':encoded,'status':status,'error':error_code,'success':status in ('partial','reconciled') and error_code is None,'complete':complete})


def mark_local_change(c, source_id, *, deleted=False):
    """Called only by authorized user source mutations, never the native collector."""
    if source_id is None or not c.execute(text("SELECT to_regclass('c0_personal_imports') IS NOT NULL")).scalar_one():
        return
    if deleted:
        c.execute(text("""UPDATE c0_personal_imports child SET state='excluded'
            FROM c0_personal_imports parent WHERE parent.source_id=:id AND parent.connector='webtop'
            AND parent.kind='message' AND child.owner_id=parent.owner_id AND child.connector=parent.connector
            AND child.instance_id=parent.instance_id AND child.kind='attachment'
            AND left(child.remote_key,length(parent.remote_key)+12)=parent.remote_key||'/attachment/'
            AND child.state NOT IN ('cleanup','removed')"""),{'id':space_uuid(source_id)})
    c.execute(text("UPDATE c0_personal_imports SET state=:state WHERE source_id=:id AND state<>'cleanup'"),
              {'id':space_uuid(source_id),'state':'excluded' if deleted else 'overridden'})


def inventory_candidates(service, *, owner_id, generation, connector, instance_id, scan_id):
    """Two matching complete traversals are necessary, never sufficient, for removal.

    The adapter must additionally authenticate a current positive control and read
    each missing exact remote item. Partial scans must never call this function.
    """
    with service.database.engine.connect() as c:
        service._fence(c,space_uuid(owner_id),generation,connector,space_uuid(instance_id))
        values={'owner':space_uuid(owner_id),'connector':connector,'instance':space_uuid(instance_id),'scan':space_uuid(scan_id)}
        rows=c.execute(text('''SELECT remote_key,kind,content_hash FROM c0_personal_imports
            WHERE owner_id=:owner AND connector=:connector AND instance_id=:instance AND last_seen_scan=:scan
            ORDER BY remote_key,kind'''),values).all()
        digest=hashlib.sha256(json.dumps([list(r) for r in rows],separators=(',',':')).encode()).hexdigest()
        previous=c.execute(text('''SELECT cursor,last_inventory,now() AS current_time FROM c0_personal_checkpoints
            WHERE owner_id=:owner AND connector=:connector AND instance_id=:instance AND generation=:generation'''),
            {**values,'generation':generation}).mappings().one_or_none()
        stable=bool(previous and previous['cursor'].get('inventory_hash')==digest and previous['last_inventory']
                    and (previous['current_time']-previous['last_inventory']).total_seconds()>=300)
        if not stable:
            return digest,[]
        missing=c.execute(text('''SELECT i.remote_key,i.kind,i.source_id,i.slot_key FROM c0_personal_imports i
            JOIN c0_sources s ON s.id=i.source_id WHERE i.owner_id=:owner AND i.connector=:connector
            AND i.instance_id=:instance AND i.last_seen_scan IS DISTINCT FROM CAST(:scan AS uuid)
            AND i.state IN ('managed','overridden') ORDER BY i.remote_key,i.kind LIMIT 20'''),values).mappings().all()
        return digest,[dict(r) for r in missing]


def queue_confirmed_removal(service, *, owner_id, generation, connector, instance_id, remote_key, kind=None):
    """Trusted collector confirmed exact source absence/loss after stable inventories."""
    if kind not in (None,'message','attachment','transcript','summary'):
        raise ValueError('invalid_personal_document_kind')
    with service.database.engine.begin() as c:
        hold_authority(c)
        service._fence(c,space_uuid(owner_id),generation,connector,space_uuid(instance_id))
        c.execute(text('''UPDATE c0_personal_imports SET state='cleanup' WHERE owner_id=:owner
            AND connector=:connector AND instance_id=:instance
            AND (remote_key=:remote OR (:connector='webtop' AND left(remote_key,length(:remote)+12)=:remote||'/attachment/'))
            AND (CAST(:kind AS text) IS NULL OR kind=:kind OR (:connector='webtop' AND :kind='message' AND kind='attachment'))
            AND state IN ('managed','overridden')'''),
            {'owner':space_uuid(owner_id),'connector':connector,'instance':space_uuid(instance_id),'remote':remote_key,'kind':kind})


def record_attachment_issues(service, *, owner_id, generation, instance_id, remote_key, issues):
    """Replace observations only after a successful exact-message read; no payloads."""
    remote_key=_label(remote_key,512)
    if type(issues) is not list or len(issues)>1000:raise ValueError('invalid_attachment_issues')
    normalized=[]
    for issue in issues:
        if issue.get('code') not in {'unsupported_attachment','too_large','source_unavailable',
            'session_unavailable','inventory_incomplete','source_not_found','capability_unverified'}:
            raise ValueError('invalid_attachment_issue')
        normalized.append((_label(issue['attachment_id'],128),issue['code']))
    with service.database.engine.begin() as c:
        hold_authority(c)
        service._fence(c,space_uuid(owner_id),generation,'webtop',space_uuid(instance_id))
        values={'owner':space_uuid(owner_id),'instance':space_uuid(instance_id),'remote':remote_key}
        c.execute(text("DELETE FROM c0_personal_issues WHERE owner_id=:owner AND connector='webtop' AND instance_id=:instance AND remote_key=:remote"),values)
        for attachment,code in normalized:
            c.execute(text("""INSERT INTO c0_personal_issues(owner_id,connector,instance_id,remote_key,attachment_id,code)
                VALUES (:owner,'webtop',:instance,:remote,:attachment,:code)
                ON CONFLICT(owner_id,connector,instance_id,remote_key,attachment_id) DO UPDATE SET code=EXCLUDED.code,observed_at=now()"""),
                {**values,'attachment':attachment,'code':code})
