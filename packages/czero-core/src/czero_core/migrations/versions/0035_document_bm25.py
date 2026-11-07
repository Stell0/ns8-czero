# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Transactional, body-free lexical derivatives for complete retained documents."""
from alembic import op
from sqlalchemy import text

revision = '0035_document_bm25'
down_revision = '0034_compilation_maintenance'
branch_labels = None
depends_on = None


def upgrade():
    # The numbered SQL normalizer is shared by backfill, writes and queries.
    # Never change v1 in place: a different normalizer requires a new backfill.
    op.execute(r"""
    CREATE FUNCTION c0_lexical_tokens_v1(value text, index_literals boolean DEFAULT false)
    RETURNS TABLE(term text, variants text[], frequency integer, originals text[])
    LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $fn$
      WITH tokens AS (
        SELECT m[1] AS original, regexp_replace(m[1],
          '([[:alpha:]])[- ]([[:digit:]])', '\1\2', 'g') AS word
        FROM regexp_matches(lower(value),
          '([[:alpha:]_]+[- ][[:digit:]]+(?:\.[[:digit:]]+)*|[[:alnum:]_]+(?:\.[[:digit:]]+)*)', 'g') m
      ), counts AS (
        SELECT word, array_agg(DISTINCT original) AS originals,
          count(*)::integer AS frequency FROM tokens GROUP BY word
      ), stems AS (
        SELECT *, ts_lexize('english_stem',word) AS en,
                  ts_lexize('italian_stem',word) AS it FROM counts
      )
      SELECT word, ARRAY(SELECT DISTINCT v FROM unnest(
          ARRAY[word] || originals || coalesce(en,'{}') || coalesce(it,'{}') ||
          CASE WHEN index_literals THEN ARRAY(
            SELECT part_variant FROM unnest(originals) original
            CROSS JOIN LATERAL regexp_split_to_table(original,'[- ]') part
            CROSS JOIN LATERAL unnest(ARRAY[part] || coalesce(ts_lexize('english_stem',part),'{}') ||
              coalesce(ts_lexize('italian_stem',part),'{}')) part_variant
          ) ELSE '{}'::text[] END) v ORDER BY v), frequency, originals
      FROM stems WHERE octet_length(word)<=2046 AND coalesce(cardinality(en),1)>0 AND coalesce(cardinality(it),1)>0
    $fn$;
    CREATE TABLE c0_lexical_documents (
      id uuid PRIMARY KEY,
      source_document_id uuid UNIQUE REFERENCES c0_documents(id) ON DELETE CASCADE,
      wiki_revision_id uuid UNIQUE REFERENCES c0_wiki_revisions(id) ON DELETE CASCADE,
      length integer NOT NULL CHECK(length>=0),
      normalizer_version integer NOT NULL DEFAULT 1 CHECK(normalizer_version=1),
      CHECK ((source_document_id IS NOT NULL)::integer +
             (wiki_revision_id IS NOT NULL)::integer = 1),
      CHECK(id=coalesce(source_document_id,wiki_revision_id))
    );
    CREATE TABLE c0_lexical_terms (
      document_id uuid NOT NULL REFERENCES c0_lexical_documents(id) ON DELETE CASCADE,
      term text NOT NULL,
      variants text[] NOT NULL,
      frequency integer NOT NULL CHECK(frequency>0),
      originals text[] NOT NULL,
      PRIMARY KEY(document_id,term)
    );
    CREATE INDEX c0_lexical_terms_variants ON c0_lexical_terms USING gin(variants);
    CREATE FUNCTION c0_index_lexical_v1() RETURNS trigger LANGUAGE plpgsql AS $fn$
    BEGIN
      DELETE FROM c0_lexical_documents WHERE id=NEW.id;
      IF TG_TABLE_NAME='c0_documents' THEN
        INSERT INTO c0_lexical_documents(id,source_document_id,length) VALUES(NEW.id,NEW.id,0);
        INSERT INTO c0_lexical_terms SELECT NEW.id,t.* FROM c0_lexical_tokens_v1(NEW.body,true) t;
      ELSE
        INSERT INTO c0_lexical_documents(id,wiki_revision_id,length) VALUES(NEW.id,NEW.id,0);
        INSERT INTO c0_lexical_terms SELECT NEW.id,t.* FROM c0_lexical_tokens_v1(NEW.title || ' ' || NEW.body,true) t;
      END IF;
      UPDATE c0_lexical_documents SET length=(SELECT coalesce(sum(frequency),0)
        FROM c0_lexical_terms WHERE document_id=NEW.id) WHERE id=NEW.id;
      RETURN NEW;
    END $fn$;
    CREATE TRIGGER c0_source_lexical AFTER INSERT OR UPDATE OF body ON c0_documents
      FOR EACH ROW EXECUTE FUNCTION c0_index_lexical_v1();
    CREATE TRIGGER c0_wiki_lexical AFTER INSERT OR UPDATE OF title,body ON c0_wiki_revisions
      FOR EACH ROW EXECUTE FUNCTION c0_index_lexical_v1();
    """)

    # One bounded statement per complete document avoids a corpus-sized SQL
    # timeout; the migration's outer transaction still publishes all or nothing.
    connection = op.get_bind()
    for table, column, body in (('c0_documents','source_document_id','body'),
                                ('c0_wiki_revisions','wiki_revision_id',"title || ' ' || body")):
        last = None
        while True:
            ids = connection.execute(text('SELECT id FROM '+table+
                (' WHERE id>:last' if last is not None else '')+' ORDER BY id LIMIT 64'),
                {'last':last}).scalars().all()
            if not ids:
                break
            for identifier in ids:
                parameters = {'id':identifier}
                connection.execute(text('INSERT INTO c0_lexical_documents(id,'+column+',length) VALUES(:id,:id,0)'), parameters)
                connection.execute(text('INSERT INTO c0_lexical_terms SELECT d.id,t.* FROM '+table+
                    ' d CROSS JOIN LATERAL c0_lexical_tokens_v1('+body+',true) t WHERE d.id=:id'), parameters)
                connection.execute(text('UPDATE c0_lexical_documents SET length=(SELECT coalesce(sum(frequency),0) '
                    'FROM c0_lexical_terms WHERE document_id=:id) WHERE id=:id'), parameters)
            last = ids[-1]


def downgrade():
    raise RuntimeError('C0 schema downgrades are not supported')
