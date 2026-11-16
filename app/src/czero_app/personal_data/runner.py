# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""One deterministic bounded native ingestion pass; no transport exposes this CLI."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import time
from uuid import UUID, uuid4

from sqlalchemy import text
from czero_core.access import AccessService
from czero_core.database import Database
from czero_core.personal_data import PersonalDataService, PersonalDataConflict, record_checkpoint, inventory_candidates, queue_confirmed_removal, record_attachment_issues
from czero_core.sources import SourceService, OriginalStore
from czero_app.job_handlers import build_registry
from .connectors import NethVoice, WebTop, Unavailable, mail_identity

RUNNER_LOCK=49403


def private_json(path, *, maximum=1024*1024):
    path=Path(path)
    descriptor=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(descriptor,'rb') as source:
        info=os.fstat(source.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or info.st_size>maximum:
            raise ValueError('invalid_personal_secret_file')
        data=source.read(maximum+1)
    if len(data)>maximum:raise ValueError('invalid_personal_secret_file')
    return json.loads(data)


class Runner:
    def __init__(self,service,*,clock=time.monotonic,before_publish=None):
        self.service=service
        self.clock=clock
        self.before_publish=before_publish

    def tick(self,snapshot,secrets,*,configure_only=False):
        service=self.service
        if configure_only:
            return self._tick(snapshot,secrets,configure_only=True)
        with service.database.engine.connect() as lock:
            if not lock.execute(text('SELECT pg_try_advisory_lock(:key)'),{'key':RUNNER_LOCK}).scalar_one():
                return {'status':'busy'}
            try:
                return self._tick(snapshot,secrets,configure_only=configure_only)
            finally:
                lock.execute(text('SELECT pg_advisory_unlock(:key)'),{'key':RUNNER_LOCK})

    def _tick(self,snapshot,secrets,*,configure_only):
        service=self.service;started=self.clock()
        config=snapshot['configuration'];services={k:config[k] for k in ('nethvoice','webtop') if config.get(k)}
        with service.database.engine.connect() as c:
            old=c.execute(text('SELECT * FROM c0_personal_config WHERE issuer=:issuer'),{'issuer':service.access.issuer}).mappings().one_or_none()
        if old is None and not config['enabled']:
            return {'status':'disabled','pending_cleanup':0}
        generation=old['generation'] if old else 0
        provider=snapshot['provider_id'] if config['enabled'] else (str(old['provider_id']) if old else snapshot['provider_id'])
        if old and str(old['provider_id'])!=provider:
            snapshot={**snapshot,'provider_verified':False,'provider_mismatch':True,'directory_mismatch':True}
            provider=str(old['provider_id'])
        current=service.configure_native(provider_id=provider,enabled=config['enabled'],services=services,expected_generation=generation)
        generation=current['generation']
        if not config['enabled']:
            self._cleanup()
            return self.status()
        if not snapshot.get('provider_verified'):
            # A native mismatch fences/cleans imports, but cannot remap identities.
            with service.database.engine.begin() as c:
                c.execute(text('SELECT pg_advisory_xact_lock(49372)'))
                c.execute(text('UPDATE c0_personal_config SET validated=false WHERE issuer=:issuer'),{'issuer':service.access.issuer})
                if snapshot.get('directory_mismatch') is True:
                    lost=c.execute(text('UPDATE c0_personal_owners SET active=false WHERE issuer=:issuer AND active RETURNING directory_id'),{'issuer':service.access.issuer}).scalars().all()
                    for directory in lost:service._revoke(c,directory)
                mismatches={kind:instance for kind,instance in services.items()
                    if kind in snapshot.get('provider_mismatches',[])}
                if snapshot.get('directory_mismatch') is True or mismatches:
                    c.execute(text("""UPDATE c0_personal_imports i SET state='cleanup' FROM c0_personal_owners o
                        WHERE i.owner_id=o.id AND o.issuer=:issuer AND i.state NOT IN ('excluded','removed')
                        AND (:directory OR CAST(:mismatches AS jsonb)->>i.connector=i.instance_id::text)"""),
                        {'issuer':service.access.issuer,'directory':snapshot.get('directory_mismatch') is True,
                         'mismatches':json.dumps(mismatches)})
            self._cleanup()
            return {'status':'provider_mismatch' if snapshot.get('provider_mismatch') is True else 'source_unavailable',**self.status()}
        owners=service.reconcile_directory(provider_id=snapshot['provider_id'],entries=snapshot['directory'],complete=snapshot.get('directory_complete') is True)
        service.validate_binding(generation=generation,provider_id=snapshot['provider_id'],services=services)
        if configure_only:
            return self.status()
        self._cleanup()
        with service.database.engine.connect() as c:
            cursor=c.execute(text('SELECT runner_cursor FROM c0_personal_config WHERE issuer=:issuer'),{'issuer':service.access.issuer}).scalar_one_or_none()
        owners=sorted((o for o in owners if o['active']),key=lambda o:o['directory_id'])
        owners=[o for o in owners if cursor is None or o['directory_id']>str(cursor)]+[o for o in owners if cursor is not None and o['directory_id']<=str(cursor)]
        for owner in owners[:5]:
            if self.clock()-started>80:break
            for kind,instance in services.items():
                if self.clock()-started>80:break
                self._owner(snapshot,secrets,owner,generation,kind,instance)
            with service.database.engine.begin() as c:
                c.execute(text('UPDATE c0_personal_config SET runner_cursor=:cursor WHERE issuer=:issuer AND generation=:generation'),
                    {'cursor':UUID(owner['directory_id']),'issuer':service.access.issuer,'generation':generation})
        self._cleanup()
        return self.status()

    def _owner(self,snapshot,secrets,owner,generation,kind,instance):
        service=self.service;adapter=None
        with service.database.engine.connect() as c:
            previous=c.execute(text('''SELECT cursor FROM c0_personal_checkpoints WHERE owner_id=:owner
                AND connector=:kind AND instance_id=:instance AND generation=:generation'''),
                {'owner':UUID(owner['id']),'kind':kind,'instance':UUID(instance),'generation':generation}).scalar_one_or_none()
        cursor=previous or {}
        # Unreleased predecessor used ten-item offsets; restart rather than skip rows.
        if cursor and cursor.get('page_size')!=5:cursor={}
        with service.database.engine.connect() as c:
            blocked=c.execute(text("""SELECT EXISTS(SELECT 1 FROM c0_accounts a JOIN c0_account_blocks b ON b.account_id=a.id
                WHERE a.issuer=:issuer AND a.account_key=:directory)"""),
                {'issuer':service.access.issuer,'directory':UUID(owner['directory_id'])}).scalar_one()
        if owner['source_identity_ambiguous']:
            record_checkpoint(service,owner_id=owner['id'],generation=generation,connector=kind,instance_id=instance,
                cursor=cursor,status='suspended',error_code='identity_ambiguous')
            return
        if blocked:
            record_checkpoint(service,owner_id=owner['id'],generation=generation,connector=kind,instance_id=instance,
                cursor=cursor,status='suspended',error_code='account_blocked')
            return
        scan_id=cursor.get('scan_id') or str(uuid4())
        try:
            endpoint=snapshot['endpoints'][kind]
            credentials=secrets.get(kind,{}).get(instance,{})
            if kind=='nethvoice':
                token=credentials.get('users',{}).get(owner['directory_id'])
                if not token:raise Unavailable('session_unavailable')
                adapter=NethVoice(endpoint,token=token,username=owner['username'])
                # Cover source-local dates ahead of UTC without knowing its timezone.
                current_end=(datetime.now(timezone.utc)+timedelta(days=1)).strftime('%Y%m%d')
                page=cursor.get('page',1)
                window_end=cursor.get('window_end',current_end)
                documents,coverage=adapter.page(start='19000101',end=window_end,page=page,size=5)
                next_cursor={'page':1 if coverage['complete'] else page+1,'window_end':current_end if coverage['complete'] else window_end,
                             'documents':len(documents),'skipped':coverage['skipped']}
            else:
                key=credentials.get('api_key')
                if not key:raise Unavailable('session_unavailable')
                # The selected WebTop domain is bound by native configuration, not an email guess.
                username=owner['username']+'@'+snapshot['mail_domain']
                adapter=WebTop(endpoint,api_key=key,username=username)
                folders=sorted(adapter.folders(),key=lambda folder:folder['id'])
                folder_hash=hashlib.sha256(json.dumps([folder['id'] for folder in folders],ensure_ascii=False).encode()).hexdigest()
                if cursor.get('folder_hash')!=folder_hash:
                    # Indices belong to one exact folder inventory, never a shifted list.
                    cursor={};scan_id=str(uuid4())
                index=cursor.get('folder_index',0);page=cursor.get('page',0)
                if index>=len(folders):index=page=0
                if not folders:
                    documents=[];coverage={'complete':True,'issues':[]}
                    next_cursor={'folder_index':0,'page':0,'documents':0}
                else:
                    documents,coverage=adapter.page(folders[index]['id'],page=page,size=5)
                    last=coverage['complete'] and index==len(folders)-1
                    next_cursor={'folder_index':0 if last else (index+1 if coverage['complete'] else index),
                                 'page':0 if coverage['complete'] else page+1,'documents':len(documents),
                                 'skipped':len(coverage['issues'])}
                    coverage['complete']=last
            if kind=='webtop':next_cursor['folder_hash']=folder_hash
            # Refresh a bounded latest page while the historical cursor advances.
            # This is extra current evidence, never an authoritative inventory.
            head_error=None
            if not coverage['complete']:
                try:
                    if kind=='nethvoice' and page>1:
                        recent,recent_coverage=adapter.page(start='19000101',end=current_end,page=1,size=5)
                    elif kind=='webtop' and folders:
                        head_index=cursor.get('head_folder_index',0)%len(folders)
                        next_cursor['head_folder_index']=(head_index+1)%len(folders)
                        if head_index!=index or page>0:
                            recent,recent_coverage=adapter.page(folders[head_index]['id'],page=0,size=5)
                        else:recent,recent_coverage=[],{}
                    else:recent,recent_coverage=[],{}
                    documents+=recent
                    coverage.setdefault('attachment_observations',[]).extend(recent_coverage.get('attachment_observations',[]))
                    next_cursor['skipped']=next_cursor.get('skipped',0)+recent_coverage.get('skipped',0)+len(recent_coverage.get('issues',[]))
                except Unavailable as error:
                    # Preserve successful historical progress; an outage is not absence.
                    head_error=error.code
                    next_cursor['skipped']=next_cursor.get('skipped',0)+1
            next_cursor['page_size']=5
            next_cursor['documents']=len(documents)
            published={};excluded_parents=set()
            for document in documents:
                if document.metadata.get('parent_import_key') in excluded_parents:continue
                if self.before_publish is not None and not self.before_publish(owner):
                    raise PersonalDataConflict()
                metadata=dict(document.metadata)
                parent=published.get(metadata.get('parent_import_key'))
                if parent:metadata['parent_source_id']=parent
                if kind=='nethvoice' and document.kind=='summary':
                    transcript=published.get(metadata.get('related_import_key'))
                    if transcript:metadata['transcript_source_id']=transcript
                receipt=service.submit(owner_id=owner['id'],generation=generation,connector=kind,instance_id=instance,
                    remote_key=document.remote_key,kind=document.kind,title=document.title,content=document.content,
                    media_type=document.media_type,metadata=metadata,scan_id=UUID(scan_id))
                if receipt.get('source_id'):published[document.remote_key]=receipt['source_id']
                if document.kind=='message' and receipt['state']=='excluded':excluded_parents.add(document.remote_key)
            for observation in coverage.get('attachment_observations',[]):
                if self.before_publish is not None and not self.before_publish(owner):raise PersonalDataConflict()
                record_attachment_issues(service,owner_id=owner['id'],generation=generation,instance_id=instance,**observation)
            next_cursor['scan_id']=scan_id
            next_cursor['scan_skipped']=cursor.get('scan_skipped',0)+next_cursor.get('skipped',0)
            next_cursor['read_verified']=cursor.get('read_verified',False) or bool(documents)
            if 'inventory_hash' in cursor:next_cursor['inventory_hash']=cursor['inventory_hash']
            inventory_complete=coverage['complete'] and (kind!='nethvoice' or window_end>=current_end)
            # Attachment payload failures do not invalidate a complete message inventory.
            # Missing items still require a stable traversal and an exact source read.
            if inventory_complete and (kind=='webtop' or not next_cursor['scan_skipped']):
                digest,candidates=inventory_candidates(service,owner_id=owner['id'],generation=generation,
                    connector=kind,instance_id=instance,scan_id=scan_id)
                # Missing API pages alone never authorize deletion, even after a stable traversal.
                if next_cursor['read_verified']:
                    for missing in candidates:
                        self._confirm_missing(adapter,kind,missing,owner,generation,instance)
                next_cursor['inventory_hash']=digest
            if coverage['complete']:
                next_cursor.pop('scan_id',None)
                next_cursor['scan_skipped']=0
                next_cursor['read_verified']=False
            # Completion refers to API traversal only; neither source has an authoritative deletion inventory.
            status='partial' if next_cursor.get('skipped') or (coverage['complete'] and cursor.get('scan_skipped')) else ('reconciled' if inventory_complete else 'backfill')
            if head_error=='session_unavailable':status='suspended'
            record_checkpoint(service,owner_id=owner['id'],generation=generation,connector=kind,instance_id=instance,
                cursor=next_cursor,status=status,error_code=head_error,complete=inventory_complete)
        except Unavailable as error:
            record_checkpoint(service,owner_id=owner['id'],generation=generation,connector=kind,instance_id=instance,
                cursor=cursor,status='suspended' if error.code=='session_unavailable' else 'degraded',error_code=error.code)
        finally:
            if adapter is not None:adapter.client.close()

    def _confirm_missing(self,adapter,kind,missing,owner,generation,instance):
        confirmed=False
        try:
            if kind=='webtop':
                slot=missing['remote_key'].split('/attachment/',1)[0]
                folder,uid,identity=json.JSONDecoder().raw_decode(slot)[0]
                message=adapter.client.read('/me/messages',params={'folder_id':folder,'uid':uid,'set_seen':'false'})
                if isinstance(message,dict):message=message.get('data',message)
                if isinstance(message,dict) and isinstance(message.get('body'),str):
                    confirmed=mail_identity(message)[0]!=identity
                    if missing['kind']=='attachment' and isinstance(message.get('attachments'),list):
                        attachment_id=missing['remote_key'].rsplit('/attachment/',1)[-1]
                        attachments=message['attachments']
                        if all(isinstance(a,dict) and isinstance(a.get('id'),str) for a in attachments):
                            confirmed=confirmed or attachment_id not in {a['id'] for a in attachments}
            else:
                try:
                    unique,linked=json.loads(missing['slot_key'])
                    if not isinstance(unique,str) or not isinstance(linked,str):raise ValueError()
                except (ValueError,TypeError):
                    raise Unavailable('identity_ambiguous') from None
                endpoint='summary' if missing['kind']=='summary' else 'transcripts'
                detail=adapter.client.read('/'+endpoint+'/'+unique,params={'id':int(missing['remote_key']),'linkedid':linked})
                if isinstance(detail,dict):detail=detail.get('data',detail)
                if isinstance(detail,dict) and detail.get('src') and detail.get('dst'):
                    confirmed=not adapter.numbers.intersection({detail['src'],detail['dst']})
        except Unavailable as error:
            confirmed=error.code=='source_not_found'
            if not confirmed:raise
        if confirmed:
            if self.before_publish is not None and not self.before_publish(owner):
                raise PersonalDataConflict()
            queue_confirmed_removal(self.service,owner_id=owner['id'],generation=generation,connector=kind,
                instance_id=instance,remote_key=missing['remote_key'],kind=missing['kind'])

    def _cleanup(self):
        self.service.cleanup(limit=50)
        with self.service.database.engine.begin() as c:
            self.service.sources.jobs.registry.get('source.cleanup').execute(c,{'version_id':str(UUID(int=0))})

    def status(self):
        service=self.service
        with service.database.engine.connect() as c:
            payload_cleanup=c.execute(text('''SELECT count(*) FROM c0_original_cleanup q JOIN c0_personal_owners o ON o.space_id=q.space_id
                WHERE o.issuer=:issuer AND NOT EXISTS(SELECT 1 FROM c0_source_versions v WHERE v.id=q.version_id)'''),{'issuer':service.access.issuer}).scalar_one()
            imports=c.execute(text('''SELECT i.state,count(*) AS count FROM c0_personal_imports i JOIN c0_personal_owners o ON o.id=i.owner_id
                WHERE o.issuer=:issuer GROUP BY i.state'''),{'issuer':service.access.issuer}).mappings().all()
            extraction=c.execute(text("""SELECT CASE WHEN v.state='queued' AND j.state='failed' THEN 'failed' ELSE v.state END AS state,count(*) AS count FROM c0_personal_imports i
                JOIN c0_personal_owners o ON o.id=i.owner_id JOIN c0_source_versions v ON v.id=i.version_id
                LEFT JOIN c0_jobs j ON j.id=v.job_id
                WHERE o.issuer=:issuer AND i.state='managed' GROUP BY 1"""),{'issuer':service.access.issuer}).mappings().all()
            issues=c.execute(text('''SELECT i.code,count(*) AS count FROM c0_personal_issues i
                JOIN c0_personal_owners o ON o.id=i.owner_id WHERE o.issuer=:issuer GROUP BY i.code'''),{'issuer':service.access.issuer}).mappings().all()
            rows=c.execute(text("""SELECT o.username,selected.key AS connector,
                CASE WHEN NOT o.active OR NOT cfg.enabled THEN 'suspended'
                     WHEN o.source_identity_ambiguous THEN 'suspended'
                     WHEN NOT cfg.validated OR p.generation IS DISTINCT FROM cfg.generation THEN 'unverified'
                     ELSE COALESCE(p.status,'unverified') END AS status,p.last_success,
                CASE WHEN p.generation=cfg.generation THEN p.last_inventory END AS last_inventory,
                CASE WHEN NOT o.active THEN 'directory_inactive' WHEN NOT cfg.enabled THEN NULL
                     WHEN o.source_identity_ambiguous THEN 'identity_ambiguous'
                     WHEN NOT cfg.validated THEN 'source_unavailable'
                     WHEN p.generation=cfg.generation THEN p.error_code END AS error_code,
                CASE WHEN p.generation=cfg.generation THEN p.cursor ELSE '{}'::jsonb END AS cursor,
                (p.generation IS DISTINCT FROM cfg.generation OR p.last_inventory IS NULL
                    OR p.last_inventory<now()-interval '24 hours') AS inventory_overdue
                FROM c0_personal_owners o JOIN c0_personal_config cfg ON cfg.issuer=o.issuer
                CROSS JOIN LATERAL jsonb_each_text(cfg.services) selected
                LEFT JOIN c0_personal_checkpoints p ON p.owner_id=o.id AND p.connector=selected.key
                    AND p.instance_id=selected.value::uuid
                WHERE o.issuer=:issuer ORDER BY o.username,selected.key LIMIT 2000"""),
                {'issuer':service.access.issuer}).mappings().all()
        from czero_core.receipts import snapshot
        return snapshot({'extraction':{r['state']:r['count'] for r in extraction},'attachment_issues':{r['code']:r['count'] for r in issues},'imports':{r['state']:r['count'] for r in imports},'users':[dict(r) for r in rows],
            'deletion_coverage':'not_authoritative','pending_payload_cleanup':payload_cleanup,'pending_cleanup':payload_cleanup+sum(r['count'] for r in imports if r['state']=='cleanup')})


def main():
    db=None
    try:
        snapshot=private_json('/var/lib/czero/personal-data-runtime.json')
        db=Database()
        access=AccessService(db,snapshot['issuer'],UUID(os.environ.get('CZERO_OWNER_LDAP_UUID') or '00000000-0000-0000-0000-000000000000'))
        if '--fence-only' in sys.argv:
            config=snapshot['configuration']
            value=PersonalDataService(db,access).fence_native(disabled=not config['enabled'],
                services={k:config[k] for k in ('nethvoice','webtop') if config.get(k)})
            with db.engine.connect() as c:
                available=c.execute(text("SELECT to_regclass('c0_personal_config') IS NOT NULL")).scalar_one()
            if available:
                originals=OriginalStore(os.environ.get('CZERO_SOURCE_DIR','/var/lib/czero/sources'))
                service=PersonalDataService(db,access,SourceService(db,access,build_registry(db,originals),originals))
                runner=Runner(service);runner._cleanup()
                value={**runner.status(),'status':value['status']}
            print(json.dumps(value))
            return 0
        secrets={} if '--configure-only' in sys.argv or not snapshot['configuration']['enabled'] or not snapshot.get('provider_verified') else private_json('/var/lib/czero/personal-data-secrets.json')
        originals=OriginalStore(os.environ.get('CZERO_SOURCE_DIR','/var/lib/czero/sources'))
        service=PersonalDataService(db,access,SourceService(db,access,build_registry(db,originals),originals))
        def current_native_binding(owner):
            # Fixed private-pipe protocol; no commands, endpoints, bodies or credentials.
            print(json.dumps({'binding_check':True,'directory_id':owner['directory_id'],'username':owner['username']}),flush=True)
            reply=sys.stdin.readline(128)
            try:return json.loads(reply)=={'allow':True}
            except ValueError:return False
        value=Runner(service,before_publish=current_native_binding).tick(snapshot,secrets,configure_only='--configure-only' in sys.argv)
        print(json.dumps(value))
        return 0
    except Exception:
        print('Personal data reconciliation unavailable',file=sys.stderr)
        return 1
    finally:
        if db:db.close()


if __name__=='__main__':sys.exit(main())
