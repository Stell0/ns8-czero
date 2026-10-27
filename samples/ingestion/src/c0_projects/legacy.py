# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Offline WikiPlant raw-layout inspection. Never import, activate or fetch."""
import csv,io,os,posixpath,re
from datetime import datetime,date,time
from pathlib import Path
from urllib.parse import urlsplit,unquote
from zoneinfo import ZoneInfo
from c0_ingest.errors import C0Error
from .adapters import safe_read,PRIVATE
from .exporting import Artifacts,canonical,relative
from .formats import load_data
from .model import sha

REFERENCE='e8dd9e7ae9b48d028cf9a735b30490749c3d8d6c'
QUEUE_FIELDS='priority id expansion_priority kind question topic_id related_page_ids parent_ids lineage_root_id origin origin_ref created_at not_before due_at status attempts priority_reason urgency_reason dedup_key refresh_occurrence_id'.split()
CALENDAR_FIELDS='id kind title start_date start_at end_at timezone date_precision status related_page_ids source_refs refresh_question priority expansion_priority recurrence lead_days origin_ref updated_at'.split()
CALENDAR_V2=CALENDAR_FIELDS+'schema_version topic_id parent_ids lineage_root_id root_reason'.split()
REQUIRED=('INSTANCE.json','config.yml','data/SCOPE.md','data/TOPICS.md','data/research_queue.csv','data/calendar.csv')
SECTIONS={'user':'User topics and interests','adjacent':'Adjacent topics','peripheral':'Peripheral topics'}
IDENTITY=re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z')


def envelope(body):
    try:value=load_data(body.strip(),'json',maximum=2*1024*1024)
    except C0Error:return None
    if type(value) is not dict:return None
    if type(value.get('body')) is str and any(key in value for key in ('title','metadata','page_id','slug')):
        return value,value['body']
    if type(value.get('content')) is dict and type(value['content'].get('body')) is str:
        return value,value['content']['body']
    return None


def markdown_parts(body):
    metadata={}
    if body.startswith('---json\n'):
        if '\n---\n' not in body:raise C0Error('incomplete_legacy_frontmatter')
        header,body=body[len('---json\n'):].split('\n---\n',1)
        metadata=load_data(header,'json',maximum=512000)
        if type(metadata) is not dict:raise C0Error('invalid_legacy_frontmatter')
    return metadata,body


def managed_wiki(metadata):
    lines=['<!-- wikiplant:managed:start -->','## Claims']
    for claim in metadata.get('claims',[]):
        lines.append('- ['+str(claim['status'])+'; '+str(claim['confidence'])+'] '+str(claim['subject'])+' — '+str(claim['predicate'])+
            ': '+str(claim['value'])+' (sources: '+(', '.join(claim['source_ids']) or 'none')+')')
    for field,heading in (('uncertainties','Uncertainties'),('relationship_ids','Relationships'),('open_questions','Open questions')):
        lines+=['','## '+heading]+['- '+value for value in metadata.get(field,[])]
    if metadata.get('type')=='project':
        lines+=['','## Project context']
        for field,label in (('goals','Goal'),('constraints','Constraint'),('assumptions','Assumption'),('dependencies','Dependency'),('decision_context','Decision')):
            lines+=['- '+label+': '+value for value in metadata.get(field,[])]
    lines.append('<!-- wikiplant:managed:end -->')
    return '\n'.join(line if line.startswith('<!-- wikiplant:managed:') else line.replace('<','&lt;').replace('>','&gt;') for line in lines)


def valid_authorization(value,instance,topic):
    if type(value) is not dict:return False
    if value.get('source_role')=='approved_configuration_history':
        if not value.get('approval_record_ref'):return False
        value=value.get('original_authorization',{})
    return (type(value) is dict and value.get('schema_version')==2 and value.get('source_role','current_user')=='current_user'
        and value.get('instance_id')==instance and value.get('operation')=='track' and value.get('target')==topic
        and all(type(value.get(key,False)) is bool for key in ('negated','quoted','hypothetical','informational'))
        and value.get('affirmative') is True and not any(value.get(key,False) for key in ('negated','quoted','hypothetical','informational'))
        and all(type(value.get(key)) is str and value[key].strip() for key in ('user_turn_ref','reason','request_sha256'))
        and bool(re.fullmatch('[a-f0-9]{64}',value['request_sha256'])))


def id_list(value):
    if (type(value) is not list or len(value)>1000 or any(type(item) is not str or not IDENTITY.fullmatch(item) for item in value)
            or len(set(value))!=len(value)):raise C0Error('invalid_legacy_reference_list')


def instant(value):
    if type(value) is not str:raise C0Error('invalid_legacy_timestamp')
    parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
    if parsed.tzinfo is None:raise C0Error('ambiguous_legacy_timestamp')
    return parsed


def configuration(value,instance):
    """Structural preparation checks, independent of executable upstream code."""
    binding=value['instance']
    if type(binding) is not dict:raise C0Error('legacy_instance_required')
    ZoneInfo(binding['timezone'])
    if binding.get('id')!=instance.get('instance_id') or not binding.get('name') or not binding.get('language'):raise C0Error('legacy_config_binding')
    if value['schema_version']==1:return
    required={'runtime','storage','skill','primary_topic_ids','schedules','initialization','queue','expansion','main_topic_refresh','topic_governance','queue_admission'}
    if not required<=set(value) or 'primary_topics' in value:raise C0Error('incomplete_legacy_config')
    if any(type(value[key]) is not dict for key in required-{'primary_topic_ids'}):raise C0Error('legacy_configuration_shapes')
    id_list(value['primary_topic_ids'])
    if not value['primary_topic_ids']:raise C0Error('legacy_primary_topics_required')
    runtime=value['runtime'];storage=value['storage'];provider=(instance.get('storage',{}) if instance.get('schema_version')==2 else
        {'provider':'google-drive','root_folder_id':instance.get('root_folder_id')})
    if type(provider) is not dict:raise C0Error('legacy_storage_binding')
    if (runtime['source_commit']!=instance['source_commit'] or runtime['release_id']!=instance['runtime_release_id']
            or not re.fullmatch('[a-f0-9]{64}',runtime['manifest_sha256']) or runtime['upgrades']!='explicit-user-request'):
        raise C0Error('legacy_runtime_disagrees')
    if storage.get('provider')!=provider.get('provider') or any(storage.get(key)!=provider.get(key) for key in
            (('root_folder_id',) if provider.get('provider')=='google-drive' else ('repository_id','repository','canonical_ref'))):
        raise C0Error('legacy_storage_disagrees')
    if value['skill']['per_instance'] is not True or type(value['skill']['routing_profile_revision']) is not int or value['skill']['routing_profile_revision']<1:
        raise C0Error('legacy_skill_binding')
    for kind in ('daily','weekly'):
        parsed=time.fromisoformat(value['schedules'][kind]['local_time'])
        if parsed.tzinfo is not None:raise C0Error('legacy_local_clock')
    if value['schedules']['weekly']['weekday'] not in ('monday','tuesday','wednesday','thursday','friday','saturday','sunday'):raise C0Error('legacy_weekday')
    for section,fields in (('initialization',{'max_research_attempts':5}),('queue',{'normal_daily_attempts':5,'urgent_daily_attempts_total':10,'urgent_priority':0})):
        if any(type(value[section].get(key)) is not int or value[section][key]!=expected for key,expected in fields.items()):raise C0Error('legacy_budget_policy')
    for section,fields in (('expansion',('child_priority_increment','max_children_per_research')),
            ('main_topic_refresh',('max_search_queries_per_topic','max_source_fetches_per_topic')),
            ('topic_governance',('max_active_adjacent_topics','max_active_peripheral_topics')),
            ('queue_admission',('max_active_automatic_items','max_new_automatic_roots_per_day','revalidate_pending_after_days','automatic_candidate_deferral_days'))):
        if any(type(value[section].get(key)) is not int or value[section][key]<1 for key in fields):raise C0Error('legacy_positive_bound_required')
    if (value['expansion']['preserve_expansion_priority'] is not True or value['main_topic_refresh']['enabled'] is not True
            or value['main_topic_refresh']['outside_queue_budget'] is not True
            or value['topic_governance']['peripheral_expiry']!='next_weekly_maintenance'):raise C0Error('legacy_governance_policy')


def calendar(value):
    zone=ZoneInfo(value['timezone']);precision=value['date_precision'];start=value['start_date']
    if (value['kind'] not in ('event','research_refresh') or value['status'] not in ('scheduled','tentative','completed','cancelled','unsupported')
            or precision not in ('date','time','month','year','unknown') or not value['title'].strip() or value['lead_days']<0):
        raise C0Error('invalid_legacy_event')
    day=(None if precision=='unknown' and not start else date.fromisoformat(start+('-01' if precision=='month' and len(start)==7
        else '-01-01' if precision=='year' and len(start)==4 else '')))
    begun=instant(value['start_at']) if value['start_at'] else None;ended=instant(value['end_at']) if value['end_at'] else None
    instant(value['updated_at'])
    if precision=='time' and (not begun or begun.astimezone(zone).date()!=day):raise C0Error('legacy_event_local_date_disagrees')
    if begun and ended and ended<begun:raise C0Error('legacy_event_end_precedes_start')
    recurrence=value['recurrence']
    if (type(recurrence) is not dict or set(recurrence)-{'frequency','interval','until'}
            or recurrence.get('frequency','none') not in ('none','daily','weekly','monthly')
            or type(recurrence.get('interval',1)) is not int or recurrence.get('interval',1)<1):raise C0Error('invalid_legacy_recurrence')
    if recurrence.get('until'):date.fromisoformat(recurrence['until'])
    if precision in ('month','year','unknown') and recurrence.get('frequency','none')!='none':raise C0Error('legacy_partial_recurrence')
    if value['kind']=='research_refresh' and (precision not in ('date','time') or not value['refresh_question']
            or value.get('schema_version')==2 and (not value.get('topic_id') or not value.get('lineage_root_id'))):
        raise C0Error('legacy_refresh_binding_required')


def scan_files(root,maximum,max_files):
    root=Path(root).absolute();result={};total=0
    if any(path.is_symlink() for path in (root,*root.parents)):raise C0Error('unsafe_legacy_snapshot_root')
    if not root.is_dir():raise C0Error('legacy_snapshot_directory_required')
    for directory,folders,files in os.walk(root,followlinks=False):
        if any((Path(directory)/name).is_symlink() for name in folders+files):raise C0Error('legacy_snapshot_symlink')
        if any(name in ('.git','__pycache__') for name in folders):raise C0Error('legacy_snapshot_is_not_a_raw_export')
        for name in sorted(files):
            if name in PRIVATE or name.endswith(('.pem','.key')):raise C0Error('legacy_snapshot_contains_credential_file')
            path=(Path(directory)/name).relative_to(root).as_posix();relative(path)
            body=safe_read(root,path,10*1024*1024);total+=len(body)
            if total>maximum or len(result)>=max_files:raise C0Error('legacy_snapshot_inventory_limit')
            result[path]={'path':path,'size':len(body),'sha256':sha(body)}
    return dict(sorted(result.items()))


def validate_snapshot(root,output,*,max_files=10000,max_bytes=100*1024*1024):
    root=Path(root).absolute();output=Path(output).absolute()
    if any(path.is_symlink() for path in (root,*root.parents,output,*output.parents)):raise C0Error('unsafe_legacy_snapshot_path')
    root=root.resolve();output=output.resolve()
    if output.is_relative_to(root):raise C0Error('legacy_validation_output_must_be_separate')
    if type(max_files) is not int or not 1<=max_files<=100000 or type(max_bytes) is not int or not 1024<=max_bytes<=1024*1024*1024:
        raise C0Error('invalid_legacy_validation_limits')
    inventory=scan_files(root,max_bytes,max_files);archive=Artifacts(output,max_bytes);findings=[];mappings=[];topics={};queue={};ids={};links=[]
    def issue(code,path,detail,severity='blocking'):
        if len(findings)>=10000:raise C0Error('legacy_finding_limit')
        findings.append({'code':code,'path':path,'detail':detail,'severity':severity})
    def read(path):
        data=safe_read(root,path,10*1024*1024)
        if sha(data)!=inventory[path]['sha256']:raise C0Error('legacy_snapshot_changed')
        return data
    for path in REQUIRED:
        if path not in inventory:issue('required_file_missing',path,'Required raw-layout file is absent.')
    instance={};config={};provider={}
    try:instance=load_data(read('INSTANCE.json').decode(),'json')
    except (C0Error,KeyError,UnicodeError):issue('invalid_instance','INSTANCE.json','Cannot validate the instance identity.')
    if type(instance) is not dict:instance={}
    legacy=instance.get('instance_id','')
    if not re.fullmatch('wp-[a-f0-9]{16}',str(legacy)) or type(instance.get('schema_version')) is not int or instance.get('schema_version') not in (1,2):
        issue('invalid_instance_binding','INSTANCE.json','Expected a stable WikiPlant instance ID and schema1/2.')
    if not re.fullmatch('[a-f0-9]{40}',str(instance.get('source_commit',''))) or not instance.get('runtime_release_id'):
        issue('invalid_runtime_identity','INSTANCE.json','Runtime release and immutable source commit are required.')
    provider=instance.get('storage',{}) if instance.get('schema_version')==2 else {'provider':'google-drive',
        **{key:instance.get(key) for key in ('root_folder_id','config_file_id','drive_map_file_id')}}
    if type(provider) is not dict or provider.get('provider') not in ('google-drive','github'):
        issue('invalid_storage_binding','INSTANCE.json','Storage binding is not a supported raw snapshot provider.')
    elif provider['provider']=='google-drive' and not all(provider.get(key) for key in ('root_folder_id','config_file_id','drive_map_file_id')):
        issue('incomplete_drive_identity','INSTANCE.json','Preserve original Drive root/config/map identifiers.')
    elif provider['provider']=='github' and not all(provider.get(key) for key in ('repository_id','repository','canonical_ref','first_verified_commit')):
        issue('incomplete_github_identity','INSTANCE.json','Preserve original repository/ref/commit identifiers.')
    try:
        config=load_data(read('config.yml').decode(),'yaml')
        if type(config) is not dict or type(config.get('schema_version')) is not int or config.get('schema_version') not in (1,2):raise C0Error('legacy_config_schema')
        configuration(config,instance)
    except (C0Error,KeyError,ValueError,TypeError,UnicodeError):issue('invalid_configuration','config.yml','Configuration identity/language/IANA timezone could not be validated.');config={}
    provenance={}
    for path in inventory:
        if not path.endswith('export-manifest.json'):continue
        try:
            manifest=load_data(read(path).decode(),'json',maximum=4*1024*1024,max_nodes=200000)
            if type(manifest) is not dict:raise C0Error('invalid_export_manifest')
            if manifest.get('kind')!='wikiplant-storage-export':continue
            if manifest.get('schema_version')!=1 or manifest.get('instance_id')!=legacy:raise C0Error('export_binding')
            for entry in manifest['files']:
                name=str(relative(entry['path']))
                if name in provenance:raise C0Error('duplicate_provider_identity')
                if name not in inventory or any(entry[key]!=inventory[name][key] for key in ('size','sha256')):raise C0Error('export_checksum')
                if not all(type(entry.get(key)) is str and entry[key] for key in ('source_object_id','source_generation','source_mime_type')):
                    raise C0Error('export_provenance')
                provenance[name]={key:entry[key] for key in ('source_object_id','source_generation','source_mime_type')}
        except (C0Error,ValueError,KeyError,TypeError,UnicodeError):issue('invalid_export_manifest',path,'Export manifest identities/checksums/provenance do not match the raw snapshot.')
    if not provenance:issue('provider_generations_unavailable','INSTANCE.json','No verified export-manifest provider generations; only actual raw hashes and metadata can be preserved.','notice')
    def emit(kind,path,value,body=None,identity=None,version=None):
        if len(mappings)>=max_files:raise C0Error('legacy_record_inventory_limit')
        identity=str(identity or next((value[key] for key in ('id','report_id','result_id','run_id','operation_id','receipt_id','cycle_id','event_id','stable_id') if value.get(key)),'path:'+path))
        version=version if version is not None else value.get('revision',value.get('version',provenance.get(path,{}).get('source_generation')))
        key=sha([legacy,kind,identity,path,version]);meta='normalized/'+key+'/metadata.json'
        archive.add(meta,canonical(value),kind=kind,resource_id=identity)
        body_path=''
        if body is not None:
            body_path='normalized/'+key+'/body.md';archive.add(body_path,body.encode(),kind=kind+'_body',resource_id=identity)
        mapping={'kind':kind,'legacy_id':identity,'legacy_instance_id':legacy,'legacy_path':path,'legacy_version':version,
            'raw_sha256':inventory[path]['sha256'],'metadata_path':meta,'body_path':body_path,
            'c0_id':None,'c0_version_id':None,'provenance':provenance.get(path,{})}
        mappings.append(mapping)
        historical=any(part in ('archive','archives','history','histories','backups') for part in Path(path).parts)
        pair=(kind,identity)
        if pair in ids and not historical and not ids[pair][1]:issue('duplicate_legacy_id',path,'Duplicate current '+kind+' identity: '+identity)
        else:ids[pair]=(path,historical)
        return mapping
    if 'data/TOPICS.md' in inventory:
        try:
            text=read('data/TOPICS.md').decode()
            if len(text.encode())>512000 or text.count('<!-- wikiplant:topic -->')>1000:raise C0Error('topic_inventory_bound')
            header=re.search(r'^<!-- wikiplant:registry (\{.*\}) -->$',text,re.M)
            meta=load_data(header[1],'json') if header else {}
            if type(meta) is not dict or meta.get('schema_version')!=2 or meta.get('instance_id')!=legacy:raise C0Error('topic_registry_binding')
            headings=list(re.finditer(r'^## (.+)$',text,re.M))
            if [match[1] for match in headings]!=list(SECTIONS.values()):raise C0Error('topic_sections')
            for index,kind in enumerate(SECTIONS):
                section=text[headings[index].end()+1:headings[index+1].start() if index+1<len(headings) else len(text)]
                pattern=r'\n?<!-- wikiplant:topic -->\n(.*?)```json\n(.*?)\n```\n<!-- /wikiplant:topic -->\n?'
                if 'wikiplant:topic' in re.sub(pattern,'',section,flags=re.S):raise C0Error('topic_markers')
                for block in re.finditer(pattern,section,re.S):
                    value=load_data(block[2],'json');identifier=value['id']
                    if type(value.get('label')) is not str or type(value.get('classification_reason')) is not str:raise C0Error('topic_text')
                    if value.get('direct_contribution') is not None and type(value['direct_contribution']) is not str:raise C0Error('topic_contribution')
                    if value.get('lifecycle') not in ('active','provisional','archived','retired'):raise C0Error('topic_lifecycle')
                    for field in ('user_anchor_ids','parent_ids'):
                        if field in value:id_list(value[field])
                    if not IDENTITY.fullmatch(identifier) or value.get('classification')!=kind or identifier in topics:raise C0Error('topic_identity')
                    def escape(item):return item.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('`','&#96;').replace('\n',' ').replace('\r',' ')
                    readable='### '+escape(value['label'])+'\n\n'+escape(value.get('direct_contribution') or value['classification_reason'])+' ('+value['lifecycle']+')\n\n'
                    if block[1]!=readable:raise C0Error('topic_readable_disagrees')
                    topics[identifier]=value;emit('topic','data/TOPICS.md',value)
                    if kind=='user' and not valid_authorization(value.get('authorization'),legacy,identifier):
                        issue('topic_scope_authorization_unverified','data/TOPICS.md','Preserved user topic lacks affirmative bound tracking provenance: '+identifier)
                    if value.get('expires_at'):instant(value['expires_at'])
                    if kind=='peripheral' and (value.get('may_spawn_research') is not False or not value.get('expires_at')):
                        issue('peripheral_lifecycle_invalid','data/TOPICS.md','Peripheral topics must remain terminal with recorded expiry.')
            for value in topics.values():
                if value['classification']=='adjacent' and (not value.get('direct_contribution') or not value.get('user_anchor_ids')
                        or any(topics.get(anchor,{}).get('classification')!='user' for anchor in value['user_anchor_ids'])):
                    issue('adjacent_anchor_invalid','data/TOPICS.md','Adjacent topic lacks a direct approved user anchor.')
            for identifier in config.get('primary_topic_ids',[]):
                if topics.get(identifier,{}).get('classification')!='user':issue('primary_scope_invalid','config.yml','Configured primary topic is not an approved user topic.')
        except (C0Error,KeyError,TypeError,ValueError,UnicodeError):issue('invalid_topic_registry','data/TOPICS.md','Managed topic metadata/readable text or identity is invalid; preserve and reconcile.')
    for path,headers,kind in (('data/research_queue.csv',(QUEUE_FIELDS,),'queue'),('data/calendar.csv',(CALENDAR_FIELDS,CALENDAR_V2),'event')):
        if path not in inventory:continue
        try:
            reader=csv.DictReader(io.StringIO(read(path).decode(),newline=''))
            if reader.fieldnames not in headers:raise C0Error('legacy_csv_header')
            for number,row in enumerate(reader):
                if number>=max_files or None in row or any(value is None for value in row.values()):raise C0Error('legacy_csv_row')
                value=dict(row)
                for key in ('related_page_ids','source_refs','parent_ids','recurrence'):
                    if key in value:value[key]=load_data(value[key],'json')
                for key in ('related_page_ids','source_refs','parent_ids'):
                    if key in value:id_list(value[key])
                for key in ('priority','expansion_priority','attempts','lead_days','schema_version'):
                    if key in value:value[key]=int(value[key])
                if not IDENTITY.fullmatch(value['id']) or not 0<=value['priority']<=100 or not 0<=value['expansion_priority']<=100:
                    raise C0Error('legacy_priority_or_identity')
                emit(kind,path,value)
                if kind=='queue':
                    for field in ('created_at','not_before','due_at'):
                        if value[field]:instant(value[field])
                    queue[value['id']]=value
                    if value['kind'] not in ('investigation','refresh','contradiction','validation') or value['status'] not in ('pending','in_progress','retry_wait','blocked','complete','deferred','archived') or value['attempts']<0:
                        issue('queue_state_invalid',path,'Preserved queue state needs explicit mapping review.')
                else:
                    calendar(value)
        except (C0Error,KeyError,TypeError,ValueError,UnicodeError,csv.Error):issue('invalid_csv',path,'CSV header, rows, dates or structured fields are invalid; raw bytes remain untouched.')
    for identifier,value in queue.items():
        if value['topic_id'] and value['topic_id'] not in topics:issue('queue_topic_missing','data/research_queue.csv','Queue topic reference is missing: '+identifier)
        for parent in value['parent_ids']:
            if parent not in queue:issue('queue_parent_missing','data/research_queue.csv','A causal parent is outside the available raw queue; retain lineage and locate its archive: '+parent)
            elif topics.get(queue[parent]['topic_id'],{}).get('classification')=='peripheral':
                issue('peripheral_descendant','data/research_queue.csv','A peripheral parent cannot create descendants.')
            elif value['expansion_priority']<queue[parent]['expansion_priority']:
                issue('lineage_depth_reset','data/research_queue.csv','Inherited expansion priority cannot decrease.')
        if value['lineage_root_id'] and value['lineage_root_id'] not in queue:
            issue('queue_root_missing','data/research_queue.csv','Original lineage root is outside the available raw queue; locate its archive.')
        if topics.get(value['topic_id'],{}).get('classification')=='peripheral' and value['parent_ids']:
            issue('peripheral_descendant','data/research_queue.csv','Peripheral lineage cannot create descendants.')
    colors={}
    for identifier in queue:
        stack=[(identifier,False)];steps=0
        while stack:
            current,finished=stack.pop();steps+=1
            if steps>max_files*10:issue('queue_lineage_bound','data/research_queue.csv','Lineage inspection incomplete.');break
            if current not in queue:continue
            if finished:colors[current]=2;continue
            if colors.get(current)==1:issue('queue_lineage_cycle','data/research_queue.csv','Causal lineage contains a cycle.');break
            if colors.get(current)==2:continue
            colors[current]=1;stack.append((current,True));stack.extend((parent,False) for parent in queue[current]['parent_ids'])
    for path in inventory:
        if path in REQUIRED or path.endswith('export-manifest.json'):continue
        if not path.startswith(('data/','installation/')):continue
        kind=next((name for prefix,name in (('data/sources/','source'),('data/wiki/','wiki'),('data/research/','research'),
            ('data/monitoring/','monitoring'),('data/reports/','report'),('data/state/','state')) if path.startswith(prefix)),'archive')
        try:
            raw=read(path);text=raw.decode();metadata={};body=None
            if path.endswith('.json'):metadata=load_data(text,'json',maximum=10*1024*1024,max_nodes=200000)
            elif path.endswith(('.md','.txt')):
                metadata,body=markdown_parts(text)
                if kind=='archive' and metadata.get('type') in ('entity','concept','project','synthesis') and metadata.get('schema_version')==2:
                    kind='wiki'
                bad=envelope(body)
                if bad:
                    issue('serialized_wiki_envelope',path,'A serialized page object needs explicit repair; proposed Markdown/metadata are separated without changing the source.')
                    metadata={**metadata,'legacy_serialized_envelope':bad[0]};body=bad[1]
                if kind=='wiki' and metadata.get('schema_version')==2 and not bad:
                    start='<!-- wikiplant:managed:start -->';end='<!-- wikiplant:managed:end -->'
                    if body.count(start)!=1 or body.count(end)!=1 or body[body.index(start):body.index(end)+len(end)]!=managed_wiki(metadata):
                        issue('wiki_managed_content_disagrees',path,'Managed claims and canonical metadata disagree; preserve for review.')
                    claim_ids=[]
                    for claim in metadata.get('claims',[]):
                        if type(claim) is not dict or not claim.get('id'):raise C0Error('legacy_claim_identity')
                        claim_ids.append(claim['id']);emit('claim',path,claim,identity=claim['id'])
                    if len(claim_ids)!=len(set(claim_ids)):issue('duplicate_claim_id',path,'Duplicate stable claim IDs require reconciliation.')
                if kind=='wiki' and len(body.encode())>131072:issue('wiki_body_requires_split',path,'Body exceeds C0 limits; plan explicit linked parts without truncation.')
                for link in re.finditer(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]|\[[^\]]*\]\(([^\s)]+)\)',body):
                    links.append((path,link[1],link[2]))
            else:metadata={'binary_or_unsupported':True,'raw_size':len(raw),'raw_sha256':sha(raw)}
            if type(metadata) is not dict:metadata={'legacy_value':metadata}
            for field in ('created_at','updated_at','retrieved_at','published_at','event_at','started_at','finished_at','retry_after'):
                stamp=metadata.get(field)
                if stamp:
                    try:
                        if type(stamp) is not str or datetime.fromisoformat(stamp.replace('Z','+00:00')).tzinfo is None:raise ValueError()
                    except ValueError:issue('timestamp_ambiguous',path,'Timestamp lacks an explicit recoverable offset: '+field)
            emit(kind,path,metadata,body)
        except UnicodeError:emit(kind,path,{'binary_or_unsupported':True,'raw_size':inventory[path]['size'],'raw_sha256':inventory[path]['sha256']})
        except (C0Error,KeyError,TypeError,ValueError):issue('invalid_raw_record',path,'Cannot normalize this record safely; raw hash/identity remains in the inventory.')
    known={mapping['legacy_id'] for mapping in mappings}
    for path,wikilink,url in links:
        if wikilink:
            if wikilink not in known:issue('unresolved_internal_link',path,'Wiki identity reference is unresolved: '+wikilink,'notice')
        elif url:
            parsed=urlsplit(url)
            if parsed.scheme or parsed.netloc or not parsed.path:continue
            target=posixpath.normpath(posixpath.join(str(Path(path).parent),unquote(parsed.path)))
            if target.startswith('../') or target.startswith('/') or target not in inventory:
                issue('broken_local_link',path,'Local file link does not resolve inside this snapshot.','notice')
    if scan_files(root,max_bytes,max_files)!=inventory:raise C0Error('legacy_snapshot_changed')
    archive.readback();blocking=sum(value['severity']=='blocking' for value in findings)
    report={'kind':'wikiplant-migration-validation','schema_version':1,'status':'BLOCKED' if blocking else 'VALIDATED',
        'legacy_instance_id':legacy,'canonical_name_from_configuration':config.get('instance',{}).get('name'),
        'reference_commit':REFERENCE,'blocking_findings':blocking,'findings':findings,'writes_c0':0,'migration_performed':False,
        'limitations':['No target binding or current C0 authorization has been established.',
            'Only actual available snapshots/provider generations are preserved; missing historical versions are not invented.',
            'Semantic assessment, unresolved references and legacy validity require migration review; no external source was fetched.']}
    plan={'kind':'wikiplant-c0-migration-preparation','schema_version':1,'legacy_instance_id':legacy,'reference_commit':REFERENCE,
        'target_project_id':None,'target_space_id':None,'migration_status':'not_started','activation_required':True,
        'instance':instance,'configuration':config,'storage_provenance':provider,'raw_files':list(inventory.values()),
        'mappings':sorted(mappings,key=lambda row:(row['kind'],row['legacy_path'],row['legacy_id'])),
        'validation':report,'files':sorted(archive.files,key=lambda entry:entry['path'])}
    artifact=archive.add('migration-manifest.json',canonical(plan),kind='migration_manifest',resource_id=legacy)
    archive.add('validation-report.json',canonical(report),kind='validation',resource_id=legacy)
    archive.add('migration-manifest.sha256',(artifact['sha256']+'\n').encode(),kind='checksum',resource_id=legacy)
    return {'status':report['status'],'legacy_instance_id':legacy,'records':len(mappings),'blocking_findings':blocking,
        'manifest_path':str(archive.root/'migration-manifest.json'),'manifest_hash':artifact['sha256'],
        'writes_c0':0,'migration_performed':False}
