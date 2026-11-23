# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Private Google connection state. Only trusted browser routes use these operations."""
import hashlib
import re
import secrets

from sqlalchemy import text

from .current_content import content_lock
from .identity import PermissionDenied, Role
from .source_http import CollectionError
from .spaces import hold_authority


def _hash(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 1024:
        raise ValueError('invalid_drive_input')
    return hashlib.sha256(value.encode()).hexdigest()


def _lock(c):
    hold_authority(c)
    content_lock(c)


class DriveAudienceChanged(PermissionDenied):
    pass


def _audience_digest(c, space):
    scope = c.execute(text("""SELECT s.revision,
        (SELECT encode(sha256(convert_to(coalesce(string_agg(account_id::text || ':' || revision::text,
          ',' ORDER BY account_id),''),'UTF8')),'hex') FROM c0_space_grants WHERE space_id=s.id) AS grants
        FROM c0_spaces s WHERE s.id=:space"""), {'space':space}).mappings().one()
    return _hash(f"{scope['revision']}:{scope['grants']}")


def _credential(c, keys):
    row = c.execute(text("""SELECT g.generation,g.credential,g.offline
        FROM c0_drive_connections g
        WHERE g.account_id=:account AND g.space_id=:space AND g.credential IS NOT NULL"""), keys).mappings().one_or_none()
    if row is None:
        raise CollectionError('drive_reconnect_required')
    return {**row,'audience':_audience_digest(c,keys['space'])}


class DriveSources:
    def _authorize_drive_mutation(self, c, actor, role):
        if (self._space_id is None or actor.session_binding is None or actor.delegation is not None
                or actor.delegated_scopes is not None or actor.api_key_binding is not None):
            raise PermissionDenied()
        return self._authorize(c, actor, role)

    def _drive_actor(self, c, actor):
        self._authorize_drive_mutation(c, actor, Role.EDITOR)
        return {'space': self._space_id, 'account': actor.user_id}

    def drive_status(self, actor):
        with self.database.engine.begin() as c:
            keys = self._drive_actor(c, actor)
            row = c.execute(text("""SELECT credential IS NOT NULL AS connected,offline,reconnect_required
                FROM c0_drive_connections WHERE account_id=:account AND space_id=:space"""), keys).mappings().one_or_none()
            return dict(row) if row else {'connected': False, 'offline': False, 'reconnect_required': False}

    def begin_drive_oauth(self, actor, *, session_key, verifier, offline=False):
        if type(offline) is not bool or not isinstance(verifier, str) or not re.fullmatch(r'[A-Za-z0-9._~-]{43,128}', verifier):
            raise ValueError('invalid_drive_input')
        state = secrets.token_urlsafe(32)
        with self.database.engine.begin() as c:
            _lock(c)
            keys = self._drive_actor(c, actor)
            c.execute(text("""DELETE FROM c0_drive_oauth_states WHERE expires_at<=now()"""))
            c.execute(text("""INSERT INTO c0_drive_oauth_states
                (account_id,space_id,state_hash,session_hash,verifier,offline,expires_at)
                VALUES (:account,:space,:state,:session,:verifier,:offline,now()+interval '10 minutes')
                ON CONFLICT(account_id,space_id) DO UPDATE SET state_hash=excluded.state_hash,
                session_hash=excluded.session_hash,verifier=excluded.verifier,offline=excluded.offline,
                expires_at=excluded.expires_at,exchanging=false"""),
                {**keys, 'state': _hash(state), 'session': _hash(session_key), 'verifier': verifier, 'offline': offline})
        return state

    def _drive_oauth_state(self, c, actor, session_key, state, *, exchanging):
        params = {'state': _hash(state), 'session': _hash(session_key), 'account': actor.user_id, 'exchanging': exchanging}
        row = c.execute(text("""SELECT space_id,verifier,offline FROM c0_drive_oauth_states
            WHERE state_hash=:state AND session_hash=:session AND account_id=:account AND expires_at>now()
            AND exchanging=:exchanging FOR UPDATE"""), params).mappings().one_or_none()
        if row is None or self._space_id not in (None, row['space_id']):
            raise PermissionDenied()
        self.in_space(row['space_id'])._drive_actor(c, actor)
        return row, params

    def take_drive_oauth(self, actor, *, session_key, state):
        with self.database.engine.begin() as c:
            _lock(c)
            row, params = self._drive_oauth_state(c, actor, session_key, state, exchanging=False)
            c.execute(text("UPDATE c0_drive_oauth_states SET exchanging=true,verifier='' WHERE state_hash=:state"), params)
            return dict(row)

    def finish_drive_oauth(self, actor, *, session_key, state, subject, credential, offline):
        if (not isinstance(credential, str) or not 1 <= len(credential) <= 32768
                or type(offline) is not bool):
            raise ValueError('invalid_drive_input')
        subject_hash = _hash(subject)
        with self.database.engine.begin() as c:
            _lock(c)
            row, params = self._drive_oauth_state(c, actor, session_key, state, exchanging=True)
            if offline != row['offline']:
                raise PermissionDenied()
            keys = {'space': row['space_id'], 'account': actor.user_id}
            old = c.execute(text("""SELECT subject_hash,credential,reconnect_required FROM c0_drive_connections
                WHERE account_id=:account AND space_id=:space"""), keys).mappings().one_or_none()
            if old and (old['credential'] is not None or old['reconnect_required']) and old['subject_hash'] != subject_hash:
                raise PermissionDenied()
            self._invalidate_drive(c, keys)
            c.execute(text("""INSERT INTO c0_drive_connections(account_id,space_id,subject_hash,credential,offline)
                VALUES (:account,:space,:subject,:credential,:offline) ON CONFLICT(account_id,space_id)
                DO UPDATE SET generation=c0_drive_connections.generation+1, credential=excluded.credential,
                offline=excluded.offline,subject_hash=excluded.subject_hash,reconnect_required=false"""),
                {**keys, 'subject': subject_hash, 'credential': credential, 'offline': offline})

    @staticmethod
    def _invalidate_drive(c, keys, *, revoked=False):
        from .automatic_sources import cancel_staged
        c.execute(text('DELETE FROM c0_drive_previews WHERE account_id=:account AND space_id=:space'), keys)
        c.execute(text('DELETE FROM c0_drive_oauth_states WHERE account_id=:account AND space_id=:space'), keys)
        ids = c.execute(text("""SELECT id FROM c0_automatic_sources WHERE kind='google_drive'
            AND owner_id=:account AND space_id=:space ORDER BY id FOR UPDATE"""), keys).scalars().all()
        for identifier in ids:
            cancel_staged(c, identifier)
        c.execute(text("""UPDATE c0_source_update_runs SET cursor='{}',lease=NULL,
            state=CASE WHEN state IN ('queued','running','pending') THEN CAST(:state AS varchar) ELSE state END,
            error_code=CASE WHEN state IN ('queued','running','pending') THEN CAST(:error AS varchar) ELSE error_code END,
            finished_at=COALESCE(finished_at,now()) WHERE definition_id=ANY(CAST(:ids AS uuid[]))"""),
            {'ids': ids, 'state': 'blocked' if revoked else 'cancelled', 'error': 'drive_reconnect_required' if revoked else None})
        c.execute(text("""UPDATE c0_automatic_sources SET enabled=false,revision=revision+1,
            next_run_at=NULL,updated_at=now() WHERE id=ANY(CAST(:ids AS uuid[]))"""), {'ids': ids})

    def disconnect_drive(self, actor):
        with self.database.engine.begin() as c:
            _lock(c)
            keys = self._drive_actor(c, actor)
            old = c.execute(text("""SELECT credential FROM c0_drive_connections
                WHERE account_id=:account AND space_id=:space"""), keys).scalar_one_or_none()
            self._invalidate_drive(c, keys)
            c.execute(text("""UPDATE c0_drive_connections SET credential=NULL,offline=false,
                generation=generation+1,reconnect_required=false WHERE account_id=:account AND space_id=:space"""), keys)
            return old

    def _expired_drive(self, keys, generation):
        """A late Google error must not revoke a replacement connection."""
        with self.database.engine.begin() as c:
            _lock(c)
            updated = c.execute(text("""UPDATE c0_drive_connections SET generation=generation+1,
                credential=NULL,offline=false,reconnect_required=true WHERE account_id=:account AND
                space_id=:space AND generation=:generation AND credential IS NOT NULL"""), {**keys, 'generation': generation})
            if updated.rowcount:
                self._invalidate_drive(c, keys, revoked=True)

    def _drive_target(self, c, actor, identifier, expected_revision):
        from .automatic_sources import UpdateConflict
        if identifier is None and expected_revision is None:
            return None
        if identifier is None or type(expected_revision) is not int or expected_revision < 1:
            raise ValueError('invalid_revision')
        row = self._row(c, identifier)
        if row['kind'] != 'google_drive' or row['owner_id'] != actor.user_id:
            raise PermissionDenied()
        if row['revision'] != expected_revision:
            raise UpdateConflict('automatic_source_conflict')
        return c.execute(text('SELECT folder_id FROM c0_drive_bindings WHERE definition_id=:id'),
                         {'id': row['id']}).scalar_one()

    def preview_drive(self, actor, *, folder_id, provider, identifier=None, expected_revision=None):
        with self.database.engine.begin() as c:
            keys = self._drive_actor(c, actor)
            stored = self._drive_target(c, actor, identifier, expected_revision)
            connection = _credential(c, keys)
            generation = connection['generation']
        folder = stored if folder_id is None else folder_id
        if not isinstance(folder, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,256}',folder):
            raise ValueError('invalid_drive_folder')
        try:
            result = provider.preview(connection['credential'], folder)
        except CollectionError as exc:
            if str(exc) == 'drive_reconnect_required':
                self._expired_drive(keys, generation)
            raise
        proof = secrets.token_urlsafe(32)
        with self.database.engine.begin() as c:
            _lock(c)
            self._drive_actor(c, actor)
            self._drive_target(c, actor, identifier, expected_revision)
            current = _credential(c, keys)
            if current['generation'] != generation or current['audience'] != connection['audience']:
                raise PermissionDenied()
            c.execute(text("DELETE FROM c0_drive_previews WHERE expires_at<=now()"))
            c.execute(text("""INSERT INTO c0_drive_previews(account_id,space_id,generation,folder_id,
                proof_hash,definition_id,revision,expires_at) VALUES (:account,:space,:generation,:folder,
                :proof,:id,:revision,now()+interval '10 minutes') ON CONFLICT(account_id,space_id)
                DO UPDATE SET generation=excluded.generation,folder_id=excluded.folder_id,proof_hash=excluded.proof_hash,
                definition_id=excluded.definition_id,revision=excluded.revision,expires_at=excluded.expires_at"""),
                {**keys, 'generation': generation, 'folder': folder, 'proof': _hash(f"{_hash(proof)}:{current['audience']}"),
                 'id': identifier, 'revision': expected_revision})
        return {**result, 'preview_token': proof}

    def save_drive(self, actor, *, preview_token, name, enabled, interval_seconds, idempotency_key,
                   identifier=None, expected_revision=None):
        return self._save(actor, kind='google_drive', config={}, name=name, enabled=enabled,
                          interval_seconds=interval_seconds, idempotency_key=idempotency_key,
                          identifier=identifier, expected_revision=expected_revision, proof_hash=_hash(preview_token))

    def _use_drive_preview(self, c, actor, proof_hash, identifier, revision, enabled):
        keys = self._drive_actor(c, actor)
        connection = _credential(c,keys)
        if enabled and not connection['offline']:
            raise ValueError('drive_offline_required')
        preview = c.execute(text("""DELETE FROM c0_drive_previews WHERE account_id=:account AND space_id=:space
            AND generation=:generation AND proof_hash=:hash AND expires_at>now()
            AND definition_id IS NOT DISTINCT FROM CAST(:id AS uuid)
            AND revision IS NOT DISTINCT FROM CAST(:revision AS bigint) RETURNING generation,folder_id"""),
            {**keys, 'hash': _hash(f"{proof_hash}:{connection['audience']}"), 'generation': connection['generation'],
             'id': identifier, 'revision': revision}).mappings().one_or_none()
        if preview is None:
            raise ValueError('drive_preview_required')
        return {**keys, **preview, 'audience':connection['audience']}

    def command_drive(self, actor, identifier, *, expected_revision, idempotency_key, action):
        if action != 'run':
            raise ValueError('invalid_source_action')
        return self._command(actor,identifier,expected_revision=expected_revision,
                             idempotency_key=idempotency_key,action=action,private_run=True)

    @staticmethod
    def _drive_worker_binding(c, definition):
        binding = c.execute(text("""SELECT b.folder_id,b.approved_audience,g.credential,g.generation
            FROM c0_drive_bindings b JOIN c0_drive_connections g USING(account_id,space_id)
            WHERE b.definition_id=:id AND b.account_id=:owner_id AND b.space_id=:space_id
            AND g.generation=b.generation AND g.credential IS NOT NULL AND g.offline"""), definition).mappings().one_or_none()
        if binding is None:
            raise PermissionDenied()
        if binding['approved_audience'] != _audience_digest(c,definition['space_id']):
            raise DriveAudienceChanged()
        return binding
