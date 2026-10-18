# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded atomic content publication through trusted domain helpers."""
from datetime import datetime

from .annotations import AnnotationService, ContentTarget
from .knowledge import KnowledgeService
from .object_schema import bounded_json
from .objects import ObjectService, ObjectConflict, ObjectNotFound
from .receipts import mutate, snapshot
from .wiki import WikiService, KnowledgeConflict, KnowledgeNotFound

# Arguments are explicit contracts, not a method/import lookup supplied by users.
_OPERATIONS = {
    'wiki.upsert': ({'slug','title','body'}, {'metadata','expected_revision'}),
    'wiki.archive': ({'page_id','expected_revision'}, set()),
    'entity.create': ({'kind','label'}, {'aliases','metadata'}),
    'entity.update': ({'entity_id','label','expected_revision'}, {'metadata'}),
    'entity.archive': ({'entity_id','expected_revision'}, set()),
    'entity.alias': ({'entity_id','value','expected_revision'}, set()),
    'entity.link': ({'entity_id','target_kind','target_id'}, set()),
    'entity.unlink': ({'entity_id','link_id'}, set()),
    'claim.create': ({'entity_id','predicate','value','evidence_chunk_ids'}, {'page_id','metadata','valid_from','valid_to'}),
    'claim.update': ({'claim_id','expected_revision','metadata'}, {'evidence_chunk_ids'}),
    'claim.archive': ({'claim_id','expected_revision'}, set()),
    'relation.create': ({'source_id','target_id','kind'}, {'metadata'}),
    'relation.update': ({'relation_id','expected_revision','metadata'}, {'deleted'}),
    'object.create': ({'type_name','data'}, {'tags'}),
    'object.update': ({'object_id','data','expected_revision'}, {'tags'}),
    'object.delete': ({'object_id','expected_revision'}, set()),
    'annotation.update': ({'target','namespace','value','expected_revision'}, set()),
}
_RESULT_PATHS = frozenset({'id','revision','content.id','content.number'})


def _references(value, index, results=None):
    if type(value) is list:
        return [_references(item, index, results) for item in value]
    if type(value) is not dict:
        return value
    if '$result' in value:
        if (set(value) != {'$result','path'} or type(value['$result']) is not int
                or not 0 <= value['$result'] < index or type(value['path']) is not str
                or value['path'] not in _RESULT_PATHS):
            raise ValueError('invalid_bundle_reference')
        if results is None:
            return value
        result = results[value['$result']]
        for field in value['path'].split('.'):
            if type(result) is not dict or field not in result:
                raise ValueError('invalid_bundle_reference')
            result = result[field]
        if (value['path'].endswith(('revision','number')) and type(result) is not int
                or value['path'].endswith('id') and type(result) is not str):
            raise ValueError('invalid_bundle_reference')
        return result
    return {key: _references(item, index, results) for key, item in value.items()}


def _operations(operations):
    if type(operations) is not list or not 1 <= len(operations) <= 25:
        raise ValueError('invalid_bundle')
    operations = bounded_json(operations, maximum=262144, object_root=False)
    for index, step in enumerate(operations):
        if type(step) is not dict or set(step) != {'operation','arguments'}:
            raise ValueError('invalid_bundle_step')
        operation, arguments = step['operation'], step['arguments']
        if type(operation) is not str or operation not in _OPERATIONS or type(arguments) is not dict:
            raise ValueError('invalid_bundle_step')
        required, optional = _OPERATIONS[operation]
        if required - arguments.keys() or arguments.keys() - required - optional:
            raise ValueError('invalid_bundle_arguments')
        _references(arguments, index)
    return operations


class _InTransaction:
    """Only trusted bundle dispatch can bind a domain callback to this connection.

    Domain methods still perform their ordinary validation and call the very same
    mutation closures. The outer receipt owns authorization, locks and commit;
    substeps neither open connections nor create individual retry receipts.
    """
    def __init__(self, database, access, connection, actor, space_id):
        super().__init__(database, access)
        self._connection, self._actor, self._space_id = connection, actor, space_id

    def _mutate(self, actor, operation, payload, key, execute):
        if actor is not self._actor:
            raise RuntimeError('untrusted_bundle_actor')
        return snapshot(execute(self._connection, actor))


class _Wiki(_InTransaction, WikiService):
    pass


class _Knowledge(_InTransaction, KnowledgeService):
    pass


class _Annotations(_InTransaction, AnnotationService):
    pass


def _dispatch(operation, arguments, wiki, knowledge, annotations, objects, connection, actor):
    args = dict(arguments)
    # Each branch binds a trusted function. Input never becomes getattr/import.
    if operation == 'wiki.upsert':
        return wiki.upsert_page(actor, **args, idempotency_key='bundle-step')
    if operation == 'wiki.archive':
        return wiki.delete_page(actor, **args, idempotency_key='bundle-step')
    if operation == 'entity.create':
        return wiki.create_entity(actor, **args, idempotency_key='bundle-step')
    if operation == 'entity.update':
        return wiki.update_entity(actor, **args, idempotency_key='bundle-step')
    if operation == 'entity.archive':
        return wiki.delete_entity(actor, **args, idempotency_key='bundle-step')
    if operation == 'entity.alias':
        return wiki.add_alias(actor, **args, idempotency_key='bundle-step')
    if operation == 'entity.link':
        return knowledge.link_entity(actor, **args, idempotency_key='bundle-step')
    if operation == 'entity.unlink':
        return knowledge.unlink_entity(actor, **args, idempotency_key='bundle-step')
    if operation == 'claim.create':
        for field in ('valid_from','valid_to'):
            if field in args and args[field] is not None:
                if type(args[field]) is not str:
                    raise ValueError('invalid_claim_time')
                try:
                    args[field] = datetime.fromisoformat(args[field])
                except ValueError:
                    raise ValueError('invalid_claim_time') from None
        return knowledge.create_claim(actor, **args, idempotency_key='bundle-step')
    if operation == 'claim.update':
        return knowledge.update_claim(actor, **args, idempotency_key='bundle-step')
    if operation == 'claim.archive':
        return knowledge.delete_claim(actor, **args, idempotency_key='bundle-step')
    if operation == 'relation.create':
        return knowledge.add_relation(actor, **args, idempotency_key='bundle-step')
    if operation == 'relation.update':
        return knowledge.update_relation(actor, **args, idempotency_key='bundle-step')
    if operation == 'annotation.update':
        target = args.get('target')
        if type(target) is not dict or set(target) != {'kind','id','revision'}:
            raise ValueError('invalid_annotation_target')
        args['target'] = ContentTarget(**target)
        return annotations.update(actor, **args, idempotency_key='bundle-step')
    # ObjectService._write is the same helper used by its atomic batch API.
    action = {'object.create':'create','object.update':'update','object.delete':'delete'}[operation]
    if 'object_id' in args:
        args['id'] = args.pop('object_id')
    return objects._write(connection, actor, {'operation':action, **args})


class KnowledgeBundleService(WikiService):
    """One space, bounded content work, one receipt and one database commit."""
    def apply(self, actor, operations, *, idempotency_key):
        operations = _operations(operations)
        def execute(connection, current):
            space = self._space(connection)
            wiki = _Wiki(self.database, self.access, connection, current, space)
            knowledge = _Knowledge(self.database, self.access, connection, current, space)
            annotations = _Annotations(self.database, self.access, connection, current, space)
            objects = ObjectService(self.database, self.access).in_space(space)
            results = []
            for index, step in enumerate(operations):
                arguments = _references(step['arguments'], index, results)
                try:
                    result = _dispatch(step['operation'], arguments, wiki, knowledge, annotations,
                        objects, connection, current)
                except ObjectConflict:
                    raise KnowledgeConflict() from None
                except ObjectNotFound:
                    raise KnowledgeNotFound() from None
                results.append(snapshot(result))
            return {'space_id': str(space), 'results': results}
        return mutate(self.database, self._authorize, actor, 'knowledge.bundle',
            {'operations': operations}, idempotency_key, execute,
            conflict=KnowledgeConflict, lock_objects=True)
