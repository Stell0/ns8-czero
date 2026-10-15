# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Original installed-library contract; identity inputs here are test-only adapters."""
import os
import time
import unittest
from uuid import uuid4
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from czero_core import Database
from czero_core.access import AccessService
from czero_core.identity import PermissionDenied, Role, VerifiedIdentity
from czero_core.migrate import migrate_database
from czero_core.objects import ObjectConflict, ObjectService


@unittest.skipUnless(os.getenv('CZERO_TEST_DATABASE_URL'), 'Requires disposable PostgreSQL/pgvector')
class IndependentPersistence(unittest.TestCase):
    def test_custom_schema_records_roles_and_repeated_packaged_migration(self):
        name='c0_example_'+uuid4().hex
        url=make_url(os.environ['CZERO_TEST_DATABASE_URL'])
        bootstrap=create_engine(url,hide_parameters=True)
        database=None
        try:
            with bootstrap.connect().execution_options(isolation_level='AUTOCOMMIT') as connection:
                connection.execute(text('CREATE DATABASE '+name))
            database=Database(url.set(database=name).render_as_string(hide_password=False))
            migrate_database(database)
            key=uuid4(); issuer='https://idp.example.test/realms/example'
            access=AccessService(database,issuer,key)
            def identity(account_key,username):
                return VerifiedIdentity(issuer,'test-'+username,str(account_key),username,username,time.time()+300)
            owner=access.resolve(identity(key,'owner'))
            objects=ObjectService(database,access)
            objects.register_type(owner,'example-project','Example project',{
                'type':'object','properties':{'title':{'type':'string','maxLength':80}},'required':['title']},['title'])
            record=objects.create(owner,'example-project',{'title':'Original application project'})
            changed=objects.update(owner,record['id'],{'title':'Reviewed project'},expected_revision=1)
            self.assertEqual(changed['revision'],2)
            with self.assertRaises(ObjectConflict):
                objects.update(owner,record['id'],{'title':'Stale overwrite'},expected_revision=1)
            reader_key=uuid4()
            with self.assertRaises(PermissionDenied):access.resolve(identity(reader_key,'reader'))
            account=next(a for a in access.list_accounts(owner) if a['username']=='reader')
            access.set_role(owner,account['id'],Role.READER)
            reader=access.resolve(identity(reader_key,'reader'))
            migrate_database(database)
            self.assertEqual(objects.get(reader,record['id'])['data'],{'title':'Reviewed project'})
            with self.assertRaises(PermissionDenied):
                objects.create(reader,'example-project',{'title':'Forbidden'})
        finally:
            if database:database.close()
            with bootstrap.connect().execution_options(isolation_level='AUTOCOMMIT') as connection:
                connection.execute(text('DROP DATABASE IF EXISTS '+name+' WITH (FORCE)'))
            bootstrap.dispose()
