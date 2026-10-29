# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Destructive latest-only conversion; preflight before any content retirement."""
from alembic import op
import sqlalchemy as sa

revision='0023_current_content'
down_revision='0022_remembered_browsers'
branch_labels=None
depends_on=None


def upgrade():
    from czero_core.retention import preflight,convert
    connection=op.get_bind()
    # ACCESS EXCLUSIVE locks fence transactions already running old code. After
    # COMMIT, protocol triggers reject old workers even if they skip readiness.
    op.execute('LOCK TABLE c0_sources,c0_source_versions,c0_wiki_pages,c0_wiki_revisions,c0_objects,c0_knowledge_receipts IN ACCESS EXCLUSIVE MODE')
    report,plan=preflight(connection)
    if report['blocked']:raise RuntimeError('latest_only_preflight_blocked_run_czero_core.retention_dry_run')
    op.add_column('c0_sources',sa.Column('current_version_id',sa.Uuid()))
    op.add_column('c0_sources',sa.Column('next_version_number',sa.Integer(),nullable=False,server_default='1'))
    op.execute("CREATE INDEX c0_sources_external_key ON c0_sources(space_id,(metadata->>'external_key'))")
    op.add_column('c0_source_versions',sa.Column('publication_title',sa.String(256)))
    op.add_column('c0_source_versions',sa.Column('publication_metadata',sa.JSON()))
    op.execute('UPDATE c0_source_versions v SET publication_title=s.title,publication_metadata=s.metadata FROM c0_sources s WHERE s.id=v.source_id')
    op.execute('''ALTER TABLE c0_sources ADD CONSTRAINT c0_source_current_space_fk FOREIGN KEY(space_id,current_version_id)
        REFERENCES c0_source_versions(space_id,id) ON DELETE SET NULL (current_version_id)''')
    op.drop_constraint('c0_source_versions_source_id_content_hash_key','c0_source_versions',type_='unique')
    op.create_table('c0_content_tombstones',
        sa.Column('space_id',sa.Uuid(),sa.ForeignKey('c0_spaces.id'),primary_key=True),
        sa.Column('kind',sa.String(24),primary_key=True),sa.Column('id',sa.Uuid(),primary_key=True),
        sa.Column('resource_id',sa.Uuid(),nullable=False),sa.Column('generation',sa.Integer(),nullable=False),
        sa.Column('content_hash',sa.String(64),nullable=False),
        sa.CheckConstraint("kind IN ('source_version','document','chunk','wiki_revision') AND generation>=1 AND content_hash ~ '^[0-9a-f]{64}$'"))
    op.create_table('c0_original_cleanup',sa.Column('version_id',sa.Uuid(),primary_key=True),
        sa.Column('space_id',sa.Uuid(),sa.ForeignKey('c0_spaces.id'),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.Column('available_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.Column('attempts',sa.Integer(),nullable=False,server_default='0'))
    # Evidence identities remain after their target disappears, without old text.
    for constraint in ('c0_evidence_links_chunk_id_fkey','c0_evidence_links_chunk_id_space_fk'):
        op.drop_constraint(constraint,'c0_evidence_links',type_='foreignkey')
    # Payload-free typed identities preserve database space/type checks when a
    # body disappears. They contain no content or reconstructable metadata.
    op.create_table('c0_content_identities',
        sa.Column('space_id',sa.Uuid(),sa.ForeignKey('c0_spaces.id',ondelete='CASCADE'),primary_key=True),
        sa.Column('kind',sa.String(24),primary_key=True),sa.Column('id',sa.Uuid(),primary_key=True),
        sa.CheckConstraint("kind IN ('source_version','wiki_revision','chunk','entity','object','claim')"))
    identity_tables=(('source_version','c0_source_versions'),('wiki_revision','c0_wiki_revisions'),
        ('chunk','c0_chunks'),('entity','c0_entities'),('object','c0_objects'),('claim','c0_claims'))
    op.execute("""CREATE FUNCTION c0_register_content_identity() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN INSERT INTO c0_content_identities(space_id,kind,id) VALUES(NEW.space_id,TG_ARGV[0],NEW.id) ON CONFLICT DO NOTHING;
        RETURN NEW; END $$""")
    for kind,table in identity_tables:
        connection.execute(sa.text('INSERT INTO c0_content_identities(space_id,kind,id) SELECT space_id,:kind,id FROM '+table),{'kind':kind})
        op.execute("CREATE TRIGGER c0_content_identity BEFORE INSERT ON "+table+" FOR EACH ROW EXECUTE FUNCTION c0_register_content_identity('"+kind+"')")
    op.execute("INSERT INTO c0_content_identities(space_id,kind,id) SELECT space_id,kind,target_id FROM c0_annotation_targets WHERE kind='object' AND object_id IS NULL ON CONFLICT DO NOTHING")
    op.add_column('c0_evidence_links',sa.Column('chunk_kind',sa.String(24),sa.Computed("'chunk'",persisted=True)))
    op.create_foreign_key('c0_evidence_links_identity_space_fk','c0_evidence_links','c0_content_identities',
        ['space_id','chunk_kind','chunk_id'],['space_id','kind','id'])
    op.create_foreign_key('c0_annotation_targets_identity_space_fk','c0_annotation_targets','c0_content_identities',
        ['space_id','kind','target_id'],['space_id','kind','id'])
    op.add_column('c0_evidence_links',sa.Column('unavailable',sa.Boolean(),nullable=False,server_default=sa.false()))
    op.add_column('c0_annotations',sa.Column('evidence_stale',sa.Boolean(),nullable=False,server_default=sa.false()))
    op.add_column('c0_claims',sa.Column('evidence_stale',sa.Boolean(),nullable=False,server_default=sa.false()))
    op.drop_constraint('c0_annotation_targets_kind','c0_annotation_targets',type_='check')
    # Preserve payload-free anchors after source/Wiki content removal.
    for kind in ('source_version','wiki_revision'):
        op.drop_constraint('c0_annotation_targets_'+kind+'_space_fk','c0_annotation_targets',type_='foreignkey')
    choices=[]
    kinds=('source_version','wiki_revision','entity','object','claim')
    for kind in kinds:
        column=kind+'_id'
        identity='('+column+' IS NULL OR '+column+'=target_id)' if kind=='object' else column+' IS NOT NULL AND '+column+'=target_id'
        choices.append("(kind='"+kind+"' AND "+identity+' AND '+' AND '.join(other+'_id IS NULL' for other in kinds if other!=kind)+')')
    op.create_check_constraint('c0_annotation_targets_kind','c0_annotation_targets',' OR '.join(choices))
    # Entity links keep their exact target identity and an explicit missing FK.
    constraints=connection.execute(sa.text("SELECT conname FROM pg_constraint WHERE conrelid='c0_entity_links'::regclass AND contype='c' AND pg_get_constraintdef(oid) LIKE '%target_kind%' ")).scalars().all()
    for name in constraints:op.drop_constraint(name,'c0_entity_links',type_='check')
    op.create_check_constraint('c0_entity_links_target_kind','c0_entity_links',"target_kind IN ('object','page','source','document','chunk')")
    choices=[]
    for kind,column in (('object','object_id'),('page','page_id'),('source','source_id'),('document','document_id'),('chunk','chunk_id')):
        identity='('+column+' IS NULL OR '+column+'=target_id)' if kind in ('object','document','chunk') else column+' IS NOT NULL AND '+column+'=target_id'
        choices.append("(target_kind='"+kind+"' AND "+identity+' AND '+' AND '.join(other+'_id IS NULL' for other in ('object','page','source','document','chunk') if other!=kind)+')')
    op.create_check_constraint('c0_entity_links_target_binding','c0_entity_links',' OR '.join(choices))
    convert(connection,plan)
    # These are protocol fences, not authentication. Normal authority is still
    # checked inside Core's transactions and selected-space boundaries.
    op.execute("""CREATE FUNCTION c0_current_writer() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN IF current_setting('c0.content_protocol',true) IS DISTINCT FROM '1' THEN
          RAISE EXCEPTION 'C0 writer protocol changed; restart with latest-only Core';
        END IF; IF TG_OP='DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF; END $$""")
    for table in ('c0_sources','c0_source_versions','c0_documents','c0_chunks','c0_wiki_pages','c0_wiki_revisions','c0_objects','c0_knowledge_receipts','c0_wiki_chunks','c0_annotation_revisions','c0_embeddings','c0_jobs','c0_job_runs'):
        op.execute('CREATE TRIGGER c0_current_writer BEFORE INSERT OR UPDATE OR DELETE ON '+table+' FOR EACH ROW EXECUTE FUNCTION c0_current_writer()')


def downgrade():
    raise RuntimeError('Restore an external pre-upgrade backup to recover removed content')
