# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Space-bound records, global schemas, atomic revisions and typed references."""
import json
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from .identity import PermissionDenied, Role
from .spaces import SpaceBound, require_scope, content_row, hold_authority, next_cursor
from .object_schema import bounded_json, name, schema_validator, tags, validate_record


class ObjectConflict(Exception):
    """A revision, type name or unique value conflicts with persisted state."""


class ObjectNotFound(Exception):
    """An admitted caller requested a nonexistent object or type."""


def _project_type(type_name, spec=None):
    from .project_schema import PREFIX, SCHEMAS
    kind = type_name.removeprefix(PREFIX)
    if type_name != PREFIX + kind or kind not in SCHEMAS:
        return False
    # A pre-existing unrelated type may collide with a new reserved name.
    # Project bootstrap rejects that collision; ordinary old records still work.
    return spec is None or (spec['schema'] == SCHEMAS[kind] and spec['unique_fields'] == ['key'])


def page(limit,offset=0):
    if type(limit) is not int or not 1<=limit<=100 or type(offset) is not int or not 0<=offset<=100000:
        raise ValueError('invalid_paging')


class ObjectService(SpaceBound):
    def __init__(self,database,access,*,reference_resolvers=None,managed_projects=False):
        self.database=database
        self.access=access
        self._managed_projects=managed_projects
        # Only trusted application code supplies these callbacks. Requests can
        # select a registered kind, never an import path, table or SQL.
        self.reference_resolvers={} if reference_resolvers is None else dict(reference_resolvers)
        for kind,resolver in self.reference_resolvers.items():
            if name(kind)=='object' or not callable(resolver):
                raise ValueError('invalid_reference_resolver')

    def _authorize(self,c,actor,role):
        return self._space_authorize(c,actor,role)

    def _authorize_types(self,c,actor,role):
        if self.access is None: raise PermissionDenied()
        current=self.access.checked_actor(c,actor)
        current.require(role)
        require_scope(current, role)
        return current

    def register_type(self,actor,type_name,label,schema,unique_fields=None):
        type_name=name(type_name)
        if _project_type(type_name):
            raise PermissionDenied()
        if type(label) is not str or not 1<=len(label.strip())<=128:
            raise ValueError('invalid_label')
        bounded_json({'label':label},maximum=1024)
        schema=schema_validator(schema).schema
        unique_fields=[] if unique_fields is None else unique_fields
        if type(unique_fields) is not list or len(unique_fields)>8 or any(type(f) is not str for f in unique_fields) or len(set(unique_fields))!=len(unique_fields):
            raise ValueError('invalid_unique_fields')
        for field in unique_fields:
            prop=schema.get('properties',{}).get(field,{})
            if prop.get('type') not in ('string','number','integer','boolean'):
                raise ValueError('invalid_unique_fields')
            if prop.get('type')=='string' and prop.get('maxLength',8192)>128:
                raise ValueError('unique_string_too_long')
        try:
            with self.database.engine.begin() as c:
                self._authorize_types(c,actor,Role.ADMIN)
                row=c.execute(text('''INSERT INTO c0_object_types(name,label,schema,unique_fields)
                    VALUES(:name,:label,CAST(:schema AS jsonb),:fields) RETURNING *'''),
                    {'name':type_name,'label':label.strip(),'schema':json.dumps(schema),'fields':unique_fields}).mappings().one()
                return dict(row)
        except IntegrityError: raise ObjectConflict() from None

    def list_types(self,actor,*,limit=100,offset=0):
        page(limit,offset)
        with self.database.engine.connect() as c:
            self._authorize_types(c,actor,Role.READER)
            return [dict(r) for r in c.execute(text('SELECT * FROM c0_object_types ORDER BY name LIMIT :limit OFFSET :offset'),
                {'limit':limit,'offset':offset}).mappings()]

    def _type(self,c,type_name):
        row=c.execute(text('SELECT * FROM c0_object_types WHERE name=:name'),{'name':name(type_name)}).mappings().one_or_none()
        if row is None: raise ObjectNotFound()
        return row

    def get_type(self,actor,type_name):
        with self.database.engine.connect() as c:
            self._authorize_types(c,actor,Role.READER)
            return dict(self._type(c,type_name))

    def _get(self,c,object_id,*,lock=False):
        sql='SELECT * FROM c0_objects WHERE space_id=:space AND id=:id'+(' FOR UPDATE' if lock else '')
        row=c.execute(text(sql),{'space':self._space(c),'id':UUID(str(object_id))}).mappings().one_or_none()
        if row is None: raise ObjectNotFound()
        return content_row(row)

    def get(self,actor,object_id):
        with self.database.engine.connect() as c:
            self._authorize(c,actor,Role.READER)
            return dict(self._get(c,object_id))

    def list(self,actor,type_name,*,limit=50,offset=0,where=None,tag=None):
        page(limit,offset)
        where={} if where is None else bounded_json(where,maximum=4096)
        if len(where)>8: raise ValueError('invalid_filter')
        if tag is not None: name(tag)
        with self.database.engine.connect() as c:
            self._authorize(c,actor,Role.READER)
            spec=self._type(c,type_name)
            if set(where)-set(spec['schema'].get('properties',{})):
                raise ValueError('invalid_filter')
            return [content_row(r) for r in c.execute(text('''SELECT * FROM c0_objects
                WHERE space_id=:space AND type_name=:name AND data @> CAST(:filter AS jsonb)
                AND (CAST(:tag AS varchar) IS NULL OR tags @> ARRAY[CAST(:tag AS varchar)])
                ORDER BY created_at,id LIMIT :limit OFFSET :offset'''),
                {'space':self._space(c),'name':type_name,'filter':json.dumps(where),'tag':tag,'limit':limit,'offset':offset}).mappings()]

    def _event(self,c,actor,row,operation):
        c.execute(text('''INSERT INTO c0_object_events(space_id,feed_cursor,object_id,type_name,revision,operation,actor_id)
            VALUES(:space,:cursor,:id,:type,:revision,:operation,:actor)'''),
            {'space':self._space(c),'cursor':next_cursor(c,self._space(c),'object'),
             'id':row['id'],'type':row['type_name'],'revision':row['revision'],'operation':operation,'actor':actor.user_id})

    def _keys(self,c,row,spec):
        c.execute(text('DELETE FROM c0_object_keys WHERE object_id=:id'),{'id':row['id']})
        for field in spec['unique_fields']:
            value=row['data'].get(field)
            if value is None: continue # Missing/optional null values are not unique keys.
            encoded=json.dumps(value,ensure_ascii=False,allow_nan=False)
            if len(encoded.encode('utf-8'))>1024: raise ValueError('unique_value_too_large')
            c.execute(text('''INSERT INTO c0_object_keys(space_id,object_id,type_name,field,value)
                VALUES(:space,:id,:type,:field,CAST(:value AS jsonb))'''),
                {'space':self._space(c),'id':row['id'],'type':row['type_name'],'field':field,'value':encoded})

    def _write(self,c,actor,operation):
        action=operation.get('operation')
        allowed={'create':{'operation','type_name','data','tags'},
                 'update':{'operation','id','expected_revision','data','tags'},
                 'delete':{'operation','id','expected_revision'}}
        if action not in allowed or set(operation)-allowed[action]: raise ValueError('invalid_operation')
        if action=='create':
            spec=self._type(c,operation.get('type_name'))
            if _project_type(spec['name'], spec) and not self._managed_projects:
                raise PermissionDenied()
            data=validate_record(spec['schema'],operation.get('data'))
            row=c.execute(text('''INSERT INTO c0_objects(space_id,id,type_name,data,tags)
                VALUES(:space,:id,:type,CAST(:data AS jsonb),:tags) RETURNING *'''),
                {'space':self._space(c),'id':uuid4(),'type':spec['name'],'data':json.dumps(data),'tags':tags(operation.get('tags',[]))}).mappings().one()
        else:
            row=self._get(c,operation.get('id'),lock=True)
            if _project_type(row['type_name'], self._type(c, row['type_name'])) and not self._managed_projects:
                raise PermissionDenied()
            revision=operation.get('expected_revision')
            if type(revision) is not int or revision<1: raise ValueError('invalid_revision')
            if row['revision']!=revision: raise ObjectConflict()
            if action=='delete':
                self._event(c,actor,row,'delete')
                c.execute(text('DELETE FROM c0_objects WHERE id=:id'),{'id':row['id']})
                return {'id':row['id'],'revision':row['revision'],'deleted':True}
            spec=self._type(c,row['type_name'])
            data=validate_record(spec['schema'],operation.get('data'))
            row=c.execute(text('''UPDATE c0_objects SET data=CAST(:data AS jsonb),tags=:tags,
                revision=revision+1,updated_at=now() WHERE id=:id RETURNING *'''),
                {'id':row['id'],'data':json.dumps(data),'tags':tags(operation.get('tags',list(row['tags'])))}).mappings().one()
        self._keys(c,row,spec)
        self._event(c,actor,row,action)
        return content_row(row)

    def batch(self,actor,operations):
        if type(operations) is not list or not 1<=len(operations)<=25 or any(type(op) is not dict for op in operations):
            raise ValueError('invalid_batch')
        # Aggregate request cap, not just a cap on each record.
        bounded_json(operations,maximum=262144,object_root=False)
        try:
            with self.database.engine.begin() as c:
                c.execute(text("SELECT pg_advisory_xact_lock(49375)"))
                hold_authority(c)
                self._authorize(c,actor,Role.EDITOR)
                # Serialize commit order before allocating event IDs, so a cursor
                # cannot skip an older uncommitted event. Lock rows consistently.
                ids=sorted({UUID(str(op['id'])) for op in operations if 'id' in op},key=str)
                for object_id in ids: self._get(c,object_id,lock=True)
                return [self._write(c,actor,op) for op in operations]
        except IntegrityError: raise ObjectConflict() from None

    def create(self,actor,type_name,data,*,record_tags=None):
        return self.batch(actor,[{'operation':'create','type_name':type_name,'data':data,'tags':[] if record_tags is None else record_tags}])[0]

    def update(self,actor,object_id,data,*,expected_revision,record_tags=None):
        op={'operation':'update','id':str(object_id),'data':data,'expected_revision':expected_revision}
        if record_tags is not None: op['tags']=record_tags
        return self.batch(actor,[op])[0]

    def delete(self,actor,object_id,*,expected_revision):
        return self.batch(actor,[{'operation':'delete','id':str(object_id),'expected_revision':expected_revision}])[0]

    def add_relation(self,actor,source_id,target_id,kind,*,source_type,target_type):
        kind=name(kind)
        try:
            with self.database.engine.begin() as c:
                c.execute(text("SELECT pg_advisory_xact_lock(49375)"))
                hold_authority(c)
                self._authorize(c,actor,Role.EDITOR)
                ids=sorted({UUID(str(source_id)),UUID(str(target_id))},key=str)
                rows={i:self._get(c,i,lock=True) for i in ids}
                source=rows[UUID(str(source_id))]; target=rows[UUID(str(target_id))]
                if source['type_name']!=source_type or target['type_name']!=target_type:
                    raise ValueError('reference_type_mismatch')
                # Endpoint locks also serialize repeated delivery with deletion.
                existing=c.execute(text('''SELECT * FROM c0_object_relations
                    WHERE source_id=:source AND target_id=:target AND kind=:kind'''),
                    {'source':source['id'],'target':target['id'],'kind':kind}).mappings().one_or_none()
                if existing: return content_row(existing)
                row=c.execute(text('''INSERT INTO c0_object_relations(space_id,id,source_id,target_id,kind)
                    VALUES(:space,:id,:source,:target,:kind) RETURNING *'''),
                    {'space':self._space(c),'id':uuid4(),'source':source['id'],'target':target['id'],'kind':kind}).mappings().one()
                self._event(c,actor,source,'relation_add')
                return content_row(row)
        except IntegrityError: raise ObjectConflict() from None

    def relations(self,actor,object_id,*,limit=50,offset=0):
        page(limit,offset)
        with self.database.engine.connect() as c:
            self._authorize(c,actor,Role.READER); self._get(c,object_id)
            return [content_row(r) for r in c.execute(text('''SELECT r.*,s.type_name AS source_type,t.type_name AS target_type
                FROM c0_object_relations r JOIN c0_objects s ON s.id=r.source_id JOIN c0_objects t ON t.id=r.target_id
                WHERE r.source_id=:id OR r.target_id=:id ORDER BY r.created_at,r.id LIMIT :limit OFFSET :offset'''),
                {'id':UUID(str(object_id)),'limit':limit,'offset':offset}).mappings()]

    def remove_relation(self,actor,relation_id):
        with self.database.engine.begin() as c:
            c.execute(text("SELECT pg_advisory_xact_lock(49375)"))
            hold_authority(c)
            self._authorize(c,actor,Role.EDITOR)
            row=c.execute(text('DELETE FROM c0_object_relations WHERE space_id=:space AND id=:id RETURNING source_id'),
                {'space':self._space(c),'id':UUID(str(relation_id))}).mappings().one_or_none()
            if row is None: raise ObjectNotFound()
            source=self._get(c,row['source_id'],lock=True)
            self._event(c,actor,source,'relation_remove')

    def events(self,actor,*,after=0,limit=50):
        page(limit)
        if type(after) is not int or after<0: raise ValueError('invalid_cursor')
        with self.database.engine.connect() as c:
            self._authorize(c,actor,Role.READER)
            return [dict(r) for r in c.execute(text('''SELECT feed_cursor AS id,object_id,type_name,revision,operation,actor_id,created_at
                FROM c0_object_events WHERE space_id=:space AND feed_cursor>:after ORDER BY feed_cursor LIMIT :limit'''),
                {'space':self._space(c),'after':after,'limit':limit}).mappings()]

    def resolve_reference(self,actor,kind,resource_id,type_name):
        """Resolve a typed object or an explicitly registered relational domain.

        A trusted resolver(connection, current_actor, UUID) returns a mapping
        with type_name and bounded JSON data, or None. It must honor its domain
        role and canonical space, use this transaction and coordinate its own deletion policy.
        M08/M09 can register their real storage after it exists. Current durable
        object relations deliberately retain real object foreign keys.
        """
        kind=name(kind); type_name=name(type_name); resource_id=UUID(str(resource_id))
        with self.database.engine.connect() as c:
            current=self._authorize(c,actor,Role.READER)
            if kind=='object':
                row=self._get(c,resource_id)
            else:
                resolver=self.reference_resolvers.get(kind)
                if resolver is None: raise ValueError('unknown_reference_kind')
                row=resolver(c,current,resource_id)
                if row is None: raise ObjectNotFound()
            if row['type_name']!=type_name: raise ValueError('reference_type_mismatch')
            return {'kind':kind,'id':resource_id,'type_name':type_name,'data':bounded_json(row['data'])}
