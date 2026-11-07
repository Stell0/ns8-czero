# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded current-publication discovery; reasoning remains with external agents."""
from uuid import uuid4

from sqlalchemy import text

from .compilation_schema import checked, digest
from .compilation_maintenance_schema import DISCOVER, ASSESS, SEMANTIC_SELECT, SEMANTIC_REVIEW
from .current_content import ContentSuperseded
from .documents import DocumentService
from .receipts import snapshot
from .sources import _uuid, SourceNotFound, SourceConflict


def _json(value):
    import json
    return json.dumps(snapshot(value), sort_keys=True, separators=(',',':'), ensure_ascii=False)


# Use a keyset over publication identity, not ingestion time or random source IDs.
# Filter physical parts after the bounded index scan so anti-joins cannot force
# a whole-space sort. They never become assessment tasks or logical coverage.
_INVENTORY = """SELECT * FROM (
  (SELECT s.id,s.compilation_publication AS marker,false AS multipart FROM c0_sources s
    WHERE s.space_id=:space AND s.compilation_publication<=:cutoff
      AND (s.compilation_publication,s.id)>(:marker,CAST(:after AS uuid))
    ORDER BY s.compilation_publication,s.id LIMIT :limit)
  UNION ALL
  (SELECT p.id,p.compilation_publication AS marker,true AS multipart FROM c0_objects p
    WHERE p.space_id=:space AND p.type_name='c0_project_source_snapshot_v1'
      AND p.compilation_publication<=:cutoff
      AND (p.compilation_publication,p.id)>(:marker,CAST(:after AS uuid))
    ORDER BY p.compilation_publication,p.id LIMIT :limit)
) originals ORDER BY marker,id LIMIT :limit"""

_HIDDEN_PART = """SELECT 1 FROM c0_objects r WHERE r.space_id=:space
  AND r.type_name IN ('c0_project_source_part_v1','c0_project_source_sync_v1')
  AND r.data->>'source_id'=:source AND (r.type_name='c0_project_source_part_v1'
    OR r.data->>'part_number'<>'1' OR EXISTS(SELECT 1 FROM c0_objects p
      WHERE p.space_id=r.space_id AND p.type_name='c0_project_source_snapshot_v1'
        AND p.data->>'connector_id'=r.data->>'connector_id'
        AND p.data->>'external_id'=r.data->>'parent_external_id')) LIMIT 1"""



class CompilationMaintenance:
    def _project_binding(self, connection, actor, run):
        """Automatic project runs share the host task and its narrower authority."""
        from .projects import ProjectService, ProjectConflict, ProjectNotFound
        projects = ProjectService(self.database,self.access,clock=self.clock).in_space(self._space_id)
        manifest = projects._find(connection,'manifest_v1','manifest',required=False)
        binding = run['data'].get('project_lease')
        if not binding:
            if manifest and run['kind'] in ('daily','weekly'):
                raise ValueError('compilation_project_lease_required')
            return None
        if not manifest:
            raise self.conflict()
        try:
            project_run = projects._lease(connection,actor,binding)
        except (ProjectConflict,ProjectNotFound):
            raise self.conflict() from None
        if (project_run['data']['workflow_type'] != run['kind']
                or manifest['data']['version'] != run['data']['project_config_version']):
            raise self.conflict()
        return manifest['data']['manifest']

    def _source_in_scope(self, connection, logical, manifest):
        if manifest is None:
            return True
        return bool(connection.execute(text('''SELECT 1 FROM c0_objects p JOIN c0_objects c
          ON c.space_id=p.space_id AND c.type_name='c0_project_connector_v1'
            AND c.data->>'connector_id'=p.data->>'connector_id'
          WHERE p.space_id=:space AND p.id=:id AND p.type_name='c0_project_source_snapshot_v1'
            AND p.data->>'connector_id'=ANY(:connectors) AND c.data->'definition'->>'enabled'='true' '''),
          {'space':self._space_id,'id':_uuid(logical),'connectors':manifest['connector_ids']}).scalar_one_or_none())

    def _cursor(self, connection, actor, profile, *, kind='inventory', create=False):
        row = connection.execute(text('''SELECT * FROM c0_compilation_runs WHERE space_id=:space
            AND kind=:kind AND cycle_key=:key'''),
            {'space':self._space_id,'kind':kind,'key':profile}).mappings().one_or_none()
        if row or not create:
            return dict(row) if row else None
        config = self._enabled(connection)
        data = {'phase':'complete','sweep':None,'marker':0,'after':str(_uuid('00000000-0000-0000-0000-000000000000')),
            'cutoff':0,'cutoff_salt':str(uuid4()),'reconcile_after':None,'counts':{},'last_page_id':None,'rounds':0}
        return dict(connection.execute(text('''INSERT INTO c0_compilation_runs(id,space_id,kind,cycle_key,state,
            policy_revision,actor_id,fencing_generation,database_epoch,attempts,started_at,updated_at,data)
            VALUES(:id,:space,:kind,:key,'cursor',:policy,:actor,1,:epoch,0,:now,:now,CAST(:data AS jsonb)) RETURNING *'''),
            {'id':uuid4(),'space':self._space_id,'kind':kind,'key':profile,'policy':config['revision'],
             'actor':actor.user_id,'epoch':self._epoch(connection),'now':self.clock(),'data':_json(data)}).mappings().one())

    def _save_cursor(self, connection, cursor):
        row = connection.execute(text('''UPDATE c0_compilation_runs SET data=CAST(:data AS jsonb),
            revision=revision+1,updated_at=:now WHERE space_id=:space AND id=:id AND revision=:revision RETURNING *'''),
            {'space':self._space_id,'id':cursor['id'],'revision':cursor['revision'],
             'data':_json(cursor['data']),'now':self.clock()}).mappings().one_or_none()
        if row is None:
            raise self.conflict()
        return dict(row)

    def _public_cursor(self, cursor):
        value=snapshot(dict(cursor))
        state=value['data']
        # Global SQL ordinals are private; unrelated spaces must not expose counts.
        cutoff=state.pop('cutoff',0)
        salt=state.pop('cutoff_salt',None)
        # A public space ID alone cannot hide a small, enumerable SQL ordinal.
        # Pre-hardening cursors expose only their existing random sweep identity.
        state['cutoff_id']=digest([str(self._space_id),salt,cutoff]) if salt else state['sweep']
        state.pop('marker',None)
        return value

    def discovery(self, actor):
        with self.database.engine.connect() as connection:
            self._authorize(connection,actor)
            rows = connection.execute(text("SELECT * FROM c0_compilation_runs WHERE space_id=:space AND state='cursor' ORDER BY kind,cycle_key LIMIT 100"),
                {'space':self._space_id}).mappings()
            return snapshot({'cursors':[self._public_cursor(r) for r in rows], 'complete_corpus_coverage':False})

    def _dependency_inputs(self, connection, logical):
        # Current target identity is included even if an older dependency was already stale.
        from .compilation import _DEP_FRESH
        rows = connection.execute(text('''SELECT DISTINCT ON (dep.target_kind,dep.target_id) dep.id,dep.target_kind,dep.target_id,dep.target_revision,
            dep.target_hash,dep.source_revision,dep.parts_hash,dep.metadata_hash,
            COALESCE(p.revision,e.revision,c.revision,r.revision) AS current_revision,
            COALESCE(p.deleted,e.deleted,c.deleted,r.deleted,true) AS deleted,
            wr.content_hash AS current_hash, ('''+_DEP_FRESH+''') AS identities_current
            FROM c0_compilation_dependencies dep
            JOIN c0_compilation_sources cs ON cs.space_id=dep.space_id AND cs.logical_document_id=dep.logical_document_id AND cs.profile_id=dep.profile_id
            LEFT JOIN c0_wiki_pages p ON dep.target_kind='page' AND p.space_id=dep.space_id AND p.id=dep.target_id
            LEFT JOIN c0_wiki_revisions wr ON wr.space_id=p.space_id AND wr.page_id=p.id AND wr.number=p.revision
            LEFT JOIN c0_entities e ON dep.target_kind='entity' AND e.space_id=dep.space_id AND e.id=dep.target_id
            LEFT JOIN c0_claims c ON dep.target_kind='claim' AND c.space_id=dep.space_id AND c.id=dep.target_id
            LEFT JOIN c0_relations r ON dep.target_kind='relation' AND r.space_id=dep.space_id AND r.id=dep.target_id
            WHERE dep.space_id=:space AND dep.logical_document_id=:id AND dep.last_verified_at IS NOT NULL
            ORDER BY dep.target_kind,dep.target_id,dep.target_revision DESC,dep.last_verified_at DESC,dep.id LIMIT 21'''), {'space':self._space_id,'id':_uuid(logical)}).mappings().all()
        return snapshot([dict(r) for r in rows])

    @staticmethod
    def _same_original(left,right):
        return {k:v for k,v in left.items() if k!='chunks'}=={k:v for k,v in right.items() if k!='chunks'}

    def _input_hash(self, binding, dependencies, profile, version):
        return digest([binding,dependencies,profile,version])

    def _assessment_children(self, connection, task):
        children = [self._task(connection,i) for i in task['assessment'].get('child_task_ids',[])]
        for child in children:
            if child['purpose']!='knowledge' or not any(s['logical_document_id']==task['source_bindings'][0]['logical_document_id']
                    and self._same_original(s,task['source_bindings'][0]) for s in child['source_bindings']):
                raise self.conflict()
            if child['state'] not in ('no_change','succeeded') or (self._publication(connection,child['id']) or {}).get('deferred'):
                return False
            try:
                self._support_task(connection,child)
            except (self.conflict,self.notfound,self.notready,ContentSuperseded,SourceNotFound,ValueError):
                return False
        return True

    def _complete_assessment(self, connection, task):
        if task['assessment'].get('findings') or not task['assessment'].get('review_complete'):
            return False
        if not self._assessment_children(connection,task):
            return False
        self._sources(connection,task['source_bindings'])
        binding = task['source_bindings'][0]
        dependencies = self._dependency_inputs(connection,binding['logical_document_id'])
        if any(not d['identities_current'] for d in dependencies):
            return False
        # New/edited targets outside the acknowledged child publications require another review.
        owned = set()
        for identifier in task['assessment'].get('child_task_ids',[]):
            publication = self._publication(connection,identifier)
            owned.update((r['kind'],r['id']) for r in (publication or {}).get('records',[]))
        baseline = task['assessment']['dependencies']
        keep = lambda rows:[r for r in rows if (r['target_kind'],r['target_id']) not in owned]
        if keep(baseline)!=keep(dependencies):
            return False
        completed_hash=self._input_hash(binding,dependencies,task['profile_id'],task['profile_version'])
        if task['assessment'].get('completed_input_hash')==completed_hash:
            return True
        task['assessment']['completed_input_hash'] = completed_hash
        connection.execute(text('''UPDATE c0_compilation_tasks SET assessment=CAST(:data AS jsonb),
            revision=revision+1,updated_at=:now WHERE space_id=:space AND id=:id'''),
            {'space':self._space_id,'id':task['id'],'data':_json(task['assessment']),'now':self.clock()})
        connection.execute(text('''UPDATE c0_compilation_sources SET last_compiled_revision=observed_revision,
            last_compiled_hash=text_hash,last_metadata_hash=metadata_hash,last_parts_hash=parts_hash,
            last_compiled_at=:now,state=:state WHERE space_id=:space AND logical_document_id=:id
              AND profile_id=:profile AND observed_revision=:revision AND parts_hash=:hash'''),
            {'space':self._space_id,'id':binding['logical_document_id'],'profile':task['profile_id'],
             'revision':binding['revision_id'],'hash':binding['parts_hash'],'now':self.clock(),
             'state':'no_change' if not owned else 'observed'})
        return True

    def _continuation_ready(self, connection, task):
        data=task['assessment']
        return bool(task['state']=='assessed' and not data['review_complete']
            and data.get('reviewed_ranges') and data['reviewed_ranges']!=data.get('starting_ranges',[])
            and set(data.get('findings',[]))<={'unread_context'} and self._assessment_children(connection,task))

    def _assessment(self, connection, actor, run, selection):
        config = self._enabled(connection)['data']
        binding,private,doc = self._source(connection,selection)
        dependencies = self._dependency_inputs(connection,binding['logical_document_id'])
        fingerprint = self._input_hash(binding,dependencies,config['profile_id'],config['profile_version'])
        family = digest(['assessment',str(self._space_id),binding['logical_document_id'],config['profile_id']])
        head = connection.execute(text('''SELECT t.* FROM c0_compilation_tasks t WHERE t.space_id=:space
            AND t.family_key=:family AND NOT EXISTS(SELECT 1 FROM c0_compilation_tasks n
              WHERE n.space_id=t.space_id AND n.predecessor_id=t.id) LIMIT 1'''),
            {'space':self._space_id,'family':family}).mappings().one_or_none()
        progress=[];children=[];continuation=False
        if head:
            head = dict(head)
            same = head['source_bindings']==[binding] and head['profile_version']==config['profile_version']
            continuation=same and self._continuation_ready(connection,head)
            if continuation:
                progress=head['assessment']['reviewed_ranges'];children=head['assessment']['child_task_ids']
            elif same and head['state']=='assessed':
                self._complete_assessment(connection,head)
                if (fingerprint in (head['assessment'].get('completed_input_hash'),head['assessment']['input_hash'])
                        or any(self._task(connection,i)['state'] not in ('succeeded','no_change','superseded','failed','conflict')
                            for i in head['assessment']['child_task_ids']) or head['assessment'].get('findings')):
                    return head,False
            elif same and (head['state']=='needs_review' or head['assessment']['input_hash']==fingerprint):
                return head,False
        active = connection.execute(text("SELECT count(*) FROM c0_compilation_tasks WHERE space_id=:space AND state IN ('queued','leased','planned','needs_review','deferred','uncertain','applied_pending_verify')"), {'space':self._space_id}).scalar_one()
        if active>=config['max_outstanding_tasks']:
            return None,False
        if head:
            connection.execute(text("UPDATE c0_compilation_tasks SET state='superseded',revision=revision+1,updated_at=:now WHERE space_id=:space AND id=:id"),
                {'space':self._space_id,'id':head['id'],'now':self.clock()})
        identifier=uuid4()
        assessment={'input_hash':fingerprint,'dependencies':dependencies,'review_complete':False,'child_task_ids':children,
            'reviewed_ranges':progress,'starting_ranges':progress,
            'findings':['target_overflow'] if len(dependencies)>20 else []}
        task=dict(connection.execute(text('''INSERT INTO c0_compilation_tasks(id,space_id,profile_id,profile_version,
            topic_key,target_key,reason,origin,dedup_key,family_key,source_bindings,target,state,policy_revision,
            predecessor_id,prior_attempts,not_before,created_at,updated_at,purpose,assessment)
            VALUES(:id,:space,:profile,:version,:topic,:target,'source_changed',:origin,:dedup,:family,
              CAST(:sources AS jsonb),'{}','queued',:policy,:previous,:prior,:now,:now,:now,
              'source_assessment',CAST(:data AS jsonb)) RETURNING *'''),
            {'id':identifier,'space':self._space_id,'profile':config['profile_id'],'version':config['profile_version'],
             'topic':'assessment/'+binding['logical_document_id'],'target':'assessment:'+binding['logical_document_id'],
             'origin':run['kind'],'dedup':digest([family,fingerprint,progress]),'family':family,'sources':_json([binding]),
             'policy':run['policy_revision'],'previous':head['id'] if head else None,
             'prior':head['attempts']+head['prior_attempts'] if head else 0,'now':self.clock(),'data':_json(assessment)}).mappings().one())
        self._observe(connection,task,[(binding,private,doc)])
        connection.execute(text('''UPDATE c0_compilation_sources SET assessment_task_id=:task
            WHERE space_id=:space AND logical_document_id=:id AND profile_id=:profile'''),
            {'space':self._space_id,'task':identifier,'id':binding['logical_document_id'],'profile':config['profile_id']})
        return task,True

    def _discover_one(self, connection, actor, run, row, manifest):
        if connection.execute(text(_HIDDEN_PART),{'space':self._space_id,'source':str(row['id'])}).scalar_one_or_none():
            connection.execute(text("UPDATE c0_compilation_sources SET state='unavailable' WHERE space_id=:space AND logical_document_id=:id"),
                {'space':self._space_id,'id':row['id']})
            return 'physical_part',None
        if not self._source_in_scope(connection,row['id'],manifest):
            return 'out_of_scope',None
        from .compilation import _SOURCE_FRESH
        previous=connection.execute(text('SELECT cs.assessment_task_id,('+_SOURCE_FRESH+''') AS fresh
            FROM c0_compilation_sources cs WHERE cs.space_id=:space AND cs.logical_document_id=:id
              AND cs.profile_id=:profile AND cs.publication_marker=:marker'''),
            {'space':self._space_id,'id':row['id'],'profile':run['data']['policy']['profile_id'],
             'marker':row.get('marker')}).mappings().one_or_none()
        if previous and previous['fresh'] and previous['assessment_task_id']:
            task=self._task(connection,previous['assessment_task_id'])
            inputs=self._dependency_inputs(connection,str(row['id']))
            fingerprint=self._input_hash(task['source_bindings'][0],inputs,task['profile_id'],task['profile_version'])
            if (task['profile_version']==run['data']['policy']['profile_version'] and fingerprint in
                    (task['assessment'].get('completed_input_hash'),task['assessment']['input_hash'])
                    and not self._continuation_ready(connection,task)):
                if task['state']=='assessed' and task['assessment'].get('completed_input_hash')!=fingerprint:
                    self._complete_assessment(connection,task)
                return 'unchanged',task
        documents=DocumentService(self.database,self.access).in_space(self._space_id)
        try:
            doc=documents._read(connection,row['id'])
            if str(doc['id'])!=str(row['id']):
                raise SourceNotFound()
            if doc['deleted']:
                raise SourceNotFound()
            if doc['state']!='ready':
                return 'incomplete',None
            chunks=connection.execute(text('''SELECT c.id FROM c0_chunks c JOIN c0_documents d
                ON d.space_id=c.space_id AND d.id=c.document_id
                WHERE c.space_id=:space AND d.version_id=ANY(CAST(:versions AS uuid[])) ORDER BY c.id LIMIT 1'''),
                {'space':self._space_id,'versions':[p['version_id'] for p in doc['parts']] if doc['multipart'] else [doc['revision_id']]}).scalars().all()
            if not chunks:
                return 'incomplete',None
            selection={'logical_document_id':str(doc['id']),'revision_id':str(doc['revision_id']),
                'chunk_ids':[str(chunks[0])]}
            task,created=self._assessment(connection,actor,run,selection)
            if task is None:
                return 'capacity',None
            return 'queued' if created else 'unchanged',task
        except (self.notfound,SourceNotFound,ContentSuperseded):
            connection.execute(text("UPDATE c0_compilation_sources SET state='unavailable',updated_at=:now WHERE space_id=:space AND logical_document_id=:id"),
                {'space':self._space_id,'id':row['id'],'now':self.clock()})
            return 'unavailable',None
        except (self.notready,SourceConflict):
            return 'incomplete',None

    def discover(self, actor, data, *, idempotency_key):
        data=checked(DISCOVER,data)
        def execute(connection,current):
            from .compilation import _DEP_FRESH
            run=self._lease(connection,current,data['lease'])
            if run['revision']!=data['expected_revision'] or run['kind']=='retrieval':
                raise self.conflict()
            manifest=self._project_binding(connection,current,run)
            config=self._enabled(connection)['data']
            limit=min(data['limit'],config['max_tasks_per_run'])
            if manifest:
                remaining=manifest['maintenance']['max_inventory']-run['data'].get('inventory_scanned',0)
                if remaining<=0:
                    return {'outcome':'deferred_project_inventory','run':snapshot(run),'cursor':None,
                        'assessment_task_ids':[],'tasks':[],'next_eligible_at':None,'complete_corpus_coverage':False}
                limit=min(limit,remaining)
            scope=digest([config['profile_id'],config['profile_version'],run['data'].get('project_config_version')])
            cursor=self._cursor(connection,current,scope,create=True)
            state=cursor['data']
            if state['phase']=='complete':
                state.update(phase='inventory',sweep=str(uuid4()),marker=0,after='00000000-0000-0000-0000-000000000000',
                    cutoff=connection.execute(text('''SELECT GREATEST(
                        COALESCE((SELECT max(compilation_publication) FROM c0_sources WHERE space_id=:space),0),
                        COALESCE((SELECT max(compilation_publication) FROM c0_objects
                          WHERE space_id=:space AND type_name='c0_project_source_snapshot_v1'),0))'''),{'space':self._space_id}).scalar_one(),
                    reconcile_after=None,counts={})
            tasks=[]
            if state['phase']=='inventory':
                rows=connection.execute(text(_INVENTORY),{'space':self._space_id,'cutoff':state['cutoff'],
                    'marker':state['marker'],'after':state['after'],'limit':limit+1}).mappings().all()
                for row in rows[:limit]:
                    outcome,task=self._discover_one(connection,current,run,row,manifest)
                    if outcome=='capacity':
                        break
                    run['data']['inventory_scanned']=run['data'].get('inventory_scanned',0)+1
                    state['marker']=row['marker'];state['after']=str(row['id'])
                    state['counts'][outcome]=state['counts'].get(outcome,0)+1
                    if task:
                        tasks.append(str(task['id']))
                        connection.execute(text('''UPDATE c0_compilation_sources SET seen_sweep_id=:sweep,publication_marker=:marker
                            WHERE space_id=:space AND logical_document_id=:id AND profile_id=:profile'''),
                            {'space':self._space_id,'id':row['id'],'profile':config['profile_id'],
                             'sweep':state['sweep'],'marker':row['marker']})
                else:
                    if len(rows)<=limit:
                        state['phase']='reconcile'
            else:
                rows=connection.execute(text('''SELECT logical_document_id AS id FROM c0_compilation_sources
                    WHERE space_id=:space AND profile_id=:profile AND seen_sweep_id IS DISTINCT FROM CAST(:sweep AS uuid)
                      AND (CAST(:after AS uuid) IS NULL OR logical_document_id>CAST(:after AS uuid))
                    ORDER BY logical_document_id LIMIT :limit'''),
                    {'space':self._space_id,'profile':config['profile_id'],'sweep':state['sweep'],
                     'after':state['reconcile_after'],'limit':limit+1}).mappings().all()
                for row in rows[:limit]:
                    outcome,task=self._discover_one(connection,current,run,row,manifest)
                    if outcome=='capacity':
                        break
                    run['data']['inventory_scanned']=run['data'].get('inventory_scanned',0)+1
                    state['reconcile_after']=str(row['id'])
                    state['counts'][outcome]=state['counts'].get(outcome,0)+1
                    if task: tasks.append(str(task['id']))
                else:
                    if len(rows)<=limit: state['phase']='complete';state['rounds']+=1
            # Bound reverse-dependency invalidation independently of source fanout.
            after=state.get('dependency_after')
            stale=connection.execute(text('''SELECT dep.id FROM c0_compilation_dependencies dep
                JOIN c0_compilation_sources cs ON cs.space_id=dep.space_id AND cs.logical_document_id=dep.logical_document_id
                  AND cs.profile_id=dep.profile_id WHERE dep.space_id=:space
                  AND (CAST(:after AS uuid) IS NULL OR dep.id>CAST(:after AS uuid))
                ORDER BY dep.id LIMIT 100'''),{'space':self._space_id,'after':after}).scalars().all()
            if stale:
                connection.execute(text('''UPDATE c0_compilation_dependencies dep SET state='stale',updated_at=:now
                    FROM c0_compilation_sources cs WHERE cs.space_id=dep.space_id AND cs.logical_document_id=dep.logical_document_id
                      AND cs.profile_id=dep.profile_id AND dep.space_id=:space AND dep.id=ANY(CAST(:ids AS uuid[]))
                      AND NOT ('''+_DEP_FRESH+''')'''),{'space':self._space_id,'ids':stale,'now':self.clock()})
            state['dependency_after']=str(stale[-1]) if len(stale)==100 else None
            cursor=self._save_cursor(connection,cursor)
            run['data']['discovery_cursor_id']=str(cursor['id'])
            reserved,retry=self._reserve_tasks(connection,current,run,run['data']['policy'],limit)
            run=self._save_run(connection,run)
            return {'outcome':'discovered_bounded','run':snapshot(run),'cursor':self._public_cursor(cursor),
                'assessment_task_ids':tasks,'tasks':reserved,'next_eligible_at':snapshot(retry),
                'complete_corpus_coverage':False}
        return self._mutate(actor,'discover',data,idempotency_key,execute,lease=data['lease'],final_lease=True)

    def assess(self, actor, data, *, idempotency_key):
        data=checked(ASSESS,data)
        def execute(connection,current):
            run=self._lease(connection,current,data['lease'])
            if run['revision']!=data['expected_revision']: raise self.conflict()
            self._project_binding(connection,current,run)
            task=self._leased_task(connection,run,data)
            if task['purpose']!='source_assessment': raise ValueError('source_assessment_required')
            original_ids={s['logical_document_id'] for s in task['source_bindings']}
            if not set(data['reviewed_source_ids'])<=original_ids or data['status']=='reviewed' and set(data['reviewed_source_ids'])!=original_ids:
                raise ValueError('complete_original_review_required')
            ranges=task['assessment'].get('reviewed_ranges',[])+data.get('reviewed_ranges',[])
            length=len(self._sources(connection,task['source_bindings'])[0][2]['body'])
            merged=[]
            for span in sorted(ranges,key=lambda r:r['start_offset']):
                if not 0<=span['start_offset']<span['end_offset']<=length:
                    raise ValueError('invalid_original_review_range')
                if merged and span['start_offset']<=merged[-1]['end_offset']:
                    merged[-1]['end_offset']=max(merged[-1]['end_offset'],span['end_offset'])
                else: merged.append(dict(span))
            if len(merged)>100: raise ValueError('review_range_budget_exhausted')
            if data['status']=='reviewed' and not data.get('reviewed_ranges'):
                merged=[{'start_offset':0,'end_offset':length}]
            if data.get('reviewed_ranges') and data['status']=='reviewed' and merged!=[{'start_offset':0,'end_offset':length}]:
                raise ValueError('complete_original_review_required')
            child_ids=list(dict.fromkeys(task['assessment']['child_task_ids']+data['child_task_ids']))
            if len(child_ids)>100: raise ValueError('assessment_child_budget_exhausted')
            if any(c['task_id']==str(task['id']) and c['state'] in ('reserved','started','uncertain') for c in run['data']['calls'].values()):
                raise self.conflict()
            task['assessment'].update(review_complete=data['status']=='reviewed',
                child_task_ids=child_ids,findings=data['findings'],reviewed_ranges=merged)
            if len(task['assessment']['dependencies'])>20 and 'target_overflow' not in data['findings']:
                raise ValueError('dependency_overflow_requires_deferral')
            # Validate even unverified child identities before saving the acknowledgement.
            for identifier in data['child_task_ids']:
                child=self._task(connection,identifier)
                if child['purpose']!='knowledge' or not all(any(self._same_original(s,c) for c in child['source_bindings']) for s in task['source_bindings']):
                    raise self.conflict()
            task['state']='assessed'
            connection.execute(text('''UPDATE c0_compilation_tasks SET state='assessed',assessment=CAST(:data AS jsonb),
                revision=revision+1,updated_at=:now WHERE space_id=:space AND id=:id'''),
                {'space':self._space_id,'id':task['id'],'data':_json(task['assessment']),'now':self.clock()})
            complete=self._complete_assessment(connection,task)
            if not complete:
                advancing=bool(data['status']=='partial' and merged!=task['assessment'].get('starting_ranges',[])
                    and set(data['findings'])<={'unread_context'})
                if not advancing and (data['status']!='reviewed' or data['findings'] or not child_ids):
                    connection.execute(text("UPDATE c0_compilation_tasks SET state='needs_review',error_code='unsupported_evidence',revision=revision+1 WHERE space_id=:space AND id=:id"),{'space':self._space_id,'id':task['id']})
                connection.execute(text("UPDATE c0_compilation_sources SET state='partial' WHERE space_id=:space AND assessment_task_id=:id"),
                    {'space':self._space_id,'id':task['id']})
            run=self._save_run(connection,run)
            return {'outcome':'assessment_verified' if complete else 'assessment_partial','run':snapshot(run),
                'task':snapshot(self._task(connection,task['id'])),'complete_corpus_coverage':False}
        def guard(connection,current):
            self._sources(connection,self._task(connection,data['task_id'])['source_bindings'])
        return self._mutate(actor,'assessment_complete',data,idempotency_key,execute,lease=data['lease'],guard=guard,final_lease=True)

    def semantic_select(self, actor, data, *, idempotency_key):
        data=checked(SEMANTIC_SELECT,data)
        def execute(connection,current):
            from .semantic_selection import select_wiki_review
            run=self._lease(connection,current,data['lease'])
            if run['revision']!=data['expected_revision'] or run['kind']!='weekly': raise self.conflict()
            if self._project_binding(connection,current,run):
                raise ValueError('use_project_semantic_select')
            if run['data'].get('semantic') and data.get('refresh_changed'):
                selection=run['data']['semantic']
                if selection['state']=='complete': raise self.conflict()
                for item in selection['items']:
                    page=self._read_record(connection,'page',item['page_id'])
                    if page['revision']!=item['revision']:
                        old={**item}
                        item.update(revision=page['revision'],wiki_revision_id=page['content']['id'],content_hash=page['content']['content_hash'])
                        selection['reviews'].pop(item['page_id'],None)
                        history=selection.setdefault('changed_selections',[])
                        if len(history)>=20: raise ValueError('semantic_refresh_budget_exhausted')
                        history.append(old)
                run=self._save_run(connection,run)
            if run['data'].get('semantic'):
                return {'outcome':'semantic_resumed','run':snapshot(run),'selection':run['data']['semantic']}
            config=run['data']['policy']
            cursor=self._cursor(connection,current,config['profile_id'],kind='semantic_cursor',create=True)
            after=cursor['data']['last_page_id'] or ''
            limit=min(config['weekly_pages'],config['daily_pages'],config['max_tasks_per_run'])
            count,rows,rotating=select_wiki_review(connection,self._space_id,after,limit,self.clock())
            items=snapshot([dict(row) for row in rows])
            # Share actual page reservations with normal publication budgets.
            reserved_items=[]
            for row in items:
                synthetic={'purpose':'knowledge','target_key':'page:'+row['page_id'],'source_bindings':[]}
                budgets=[self._budget(connection,run['day_budget_id']),self._budget(connection,run['week_budget_id'])]
                if any(not self._reservation_fits(connection,b,synthetic,config) for b in budgets):
                    break
                reserved_items.append(row)
                identity=digest(['semantic_reserve',str(run['id']),row['page_id']])
                self._event(connection,current,identity,identity,'semantic_select','reserved',run=run,
                    kind='semantic_reserve',metrics={'document_ids':[],'target_keys':[synthetic['target_key']]})
            if items and not reserved_items:
                return {'outcome':'deferred_budget','run':snapshot(run),'selection':None}
            items=reserved_items
            selection={'items':items,'reviews':{},'inventory_total':count,'cursor_id':str(cursor['id']),
                'cursor_revision':cursor['revision'],'cursor_before':after,'cursor_after':rotating if items else after,
                'state':'pending' if items else 'complete','complete_corpus_coverage':False}
            run['data']['semantic']=selection
            run=self._save_run(connection,run)
            return {'outcome':'semantic_selected','run':snapshot(run),'selection':selection}
        return self._mutate(actor,'semantic_select',data,idempotency_key,execute,lease=data['lease'],final_lease=True)

    def semantic_review(self, actor, data, *, idempotency_key):
        data=checked(SEMANTIC_REVIEW,data)
        def execute(connection,current):
            run=self._lease(connection,current,data['lease'])
            if run['revision']!=data['expected_revision']: raise self.conflict()
            if self._project_binding(connection,current,run): raise ValueError('use_project_semantic_review')
            selection=run['data'].get('semantic')
            if not selection or selection['state']=='complete': raise self.conflict()
            item=next((r for r in selection['items'] if r['page_id']==data['page_id']),None)
            if item is None: raise self.conflict()
            page=self._read_record(connection,'page',data['page_id'])
            if page['revision']!=data['revision'] or page['content']['id']!=data['content_id'] or page['content']['content_hash']!=data['content_hash']:
                raise self.conflict()
            selected=(item['revision'],item['wiki_revision_id'],item['content_hash'])
            observed=(data['revision'],data['content_id'],data['content_hash'])
            if selected!=observed:
                supported=False
                for identifier in data['child_task_ids']:
                    child=self._task(connection,identifier)
                    target=child['target']
                    publication=self._publication(connection,identifier)
                    supported=supported or bool(target and target['id']==data['page_id']
                        and (target['revision'],target['content_id'],target['content_hash'])==selected
                        and publication and any(r['kind']=='page' and r['id']==data['page_id']
                            and (r['revision'],r['content_id'],r['content_hash'])==observed for r in publication['records']))
                if not supported: raise self.conflict()
            self._sources(connection,data['source_bindings'])
            if data['status']=='reviewed' and not data['source_bindings']:
                raise ValueError('original_evidence_review_required')
            usage=data['usage_reservation_id']
            if usage:
                call=run['data']['calls'].get(usage)
                if not call or call['state']!='returned': raise self.conflict()
                semantic=call.get('semantic')
                if semantic:
                    target=semantic['target']
                    if (target['id']!=data['page_id'] or (target['revision'],target['content_id'],target['content_hash'])!=selected
                            or semantic['source_hash']!=digest(data['source_bindings'])):
                        raise self.conflict()
                else:
                    task=self._task(connection,call['task_id'])
                    if not all(s in task['source_bindings'] for s in data['source_bindings']): raise self.conflict()
            for identifier in data['child_task_ids']:
                child=self._task(connection,identifier)
                if child['purpose']!='knowledge' or not child['target'] or child['target']['id']!=data['page_id']:
                    raise self.conflict()
                if child['state'] not in ('succeeded','no_change') and data['status']=='reviewed': raise self.conflict()
                self._support_task(connection,child)
            selection['reviews'][data['page_id']]={'status':data['status'],
                'observed':{'kind':'page','id':data['page_id'],'revision':data['revision'],'content_id':data['content_id'],'content_hash':data['content_hash']},
                'source_hash':digest(data['source_bindings']),
                'source_selections':[{'logical_document_id':s['logical_document_id'],'revision_id':s['revision_id'],
                    'chunk_ids':[c['chunk_id'] for c in s['chunks']]} for s in data['source_bindings']],
                'child_task_ids':data['child_task_ids'],'usage_reservation_id':usage}
            if len(selection['reviews'])==len(selection['items']) and all(r['status']=='reviewed' for r in selection['reviews'].values()):
                self._semantic_current(connection,selection)
                cursor=self._cursor(connection,current,run['data']['policy']['profile_id'],kind='semantic_cursor')
                if cursor['revision']!=selection['cursor_revision']: raise self.conflict()
                cursor['data'].update(last_page_id=selection['cursor_after'],rounds=cursor['data']['rounds']+1)
                self._save_cursor(connection,cursor)
                selection['state']='complete'
            run=self._save_run(connection,run)
            return {'outcome':'semantic_review_saved','run':snapshot(run),'selection':selection}
        def guard(connection,current):
            self._sources(connection,data['source_bindings'])
            self._target(connection,{'id':data['page_id'],'revision':data['revision'],
                'content_id':data['content_id'],'content_hash':data['content_hash']})
        return self._mutate(actor,'semantic_review',data,idempotency_key,execute,lease=data['lease'],guard=guard,final_lease=True)

    def _semantic_current(self, connection, selection):
        for review in selection['reviews'].values():
            self._target(connection,review['observed'])
            bindings=[self._source(connection,s)[0] for s in review['source_selections']]
            if digest(bindings)!=review['source_hash']: raise self.conflict()
            for identifier in review['child_task_ids']:
                child=self._task(connection,identifier)
                if child['state'] not in ('no_change','succeeded'): raise self.conflict()
                self._support_task(connection,child)
