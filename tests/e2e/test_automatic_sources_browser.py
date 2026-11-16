# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
from urllib.parse import urlencode
from playwright.sync_api import expect
from test_nebula_theme import assert_accessibility


def test_automatic_source_form_theme_keyboard_and_real_persistence(live,browser):
    browser.context.clear_cookies();browser.goto(live.origin+'/auth/login')
    browser.goto(live.origin+'/automatic-sources?'+urlencode({'space_id':live.space}))
    expect(browser.get_by_role('heading',name='Automatic sources',exact=True)).to_be_visible()
    browser.get_by_role('button',name='Add automatic source',exact=True).press('Enter')
    dialog=browser.get_by_role('dialog')
    for theme in ('light','dark'):
        browser.emulate_media(color_scheme=theme)
        for width in (1440,390):
            browser.set_viewport_size({'width':width,'height':1000})
            assert_accessibility(browser)
            assert browser.evaluate('document.documentElement.scrollWidth <= innerWidth')
    dialog.get_by_role('textbox',name='Title',exact=True).fill('Public docs fixture')
    dialog.get_by_role('button',name='GitHub',exact=True).click()
    dialog.get_by_role('textbox',name='Repositories (owner/name)',exact=True).fill('synthetic/example')
    dialog.get_by_role('button',name='Save configuration',exact=True).click()
    expect(dialog).to_have_count(0)
    expect(browser.get_by_text('Public docs fixture',exact=False)).to_be_visible()
    browser.reload()
    expect(browser.get_by_text('Public docs fixture',exact=False)).to_be_visible()
    # Reader visibility uses actual signed SSO and selected-space grants.
    browser.context.clear_cookies()
    browser.context.add_cookies([{'name':'fixture_persona','value':'reader','url':live.origin}])
    browser.goto(live.origin+'/auth/login')
    browser.goto(live.origin+'/automatic-sources?'+urlencode({'space_id':live.space}))
    expect(browser.get_by_text('Public docs fixture',exact=False)).to_be_visible()
    expect(browser.get_by_role('button',name='Add automatic source',exact=True)).to_have_count(0)
    expect(browser.get_by_role('button',name='Edit source',exact=True)).to_have_count(0)
    browser.context.clear_cookies();browser.goto(live.origin+'/auth/login')
    browser.goto(live.origin+'/automatic-sources?'+urlencode({'space_id':live.space}))
    browser.get_by_role('button',name='Remove configuration',exact=True).click()
    browser.get_by_role('dialog').get_by_role('button',name='Remove configuration',exact=True).press('Enter')
    expect(browser.get_by_role('dialog')).to_have_count(0)
    expect(browser.get_by_text('Public docs fixture',exact=False)).to_have_count(0)


def test_native_worker_collects_pinned_public_github_original(live,browser,tmp_path):
    import os
    import subprocess
    import sys
    from sqlalchemy import text
    from czero_core.database import Database
    revision='6845d45252a73327b7eabce38fe28fdc81e3e5d0'
    expected='5fa2fb198fbdc0b194d618c210b2c0e2c9397294cb94496b7fd4cf333a0cb680'
    owner=live.rest.get('/api/v1/me').json()
    assert owner['is_owner']
    database=Database(os.environ['CZERO_TEST_DATABASE_URL'])
    try:
        with database.engine.connect() as c:
            identity=c.execute(text('SELECT issuer,account_key FROM c0_accounts WHERE id=:id'),{'id':owner['id']}).mappings().one()
    finally:database.close()
    live.pause_worker()
    result=live.rest.post('/api/v1/automatic-sources',params={'space_id':live.space},json={
        'name':'Pinned public README','kind':'github','config':{'repositories':['Stell0/ns8-czero'],'include':['files'],'paths':['README.md'],'ref':revision},
        'enabled':True,'interval_seconds':None,'idempotency_key':'pinned-public-readme'})
    assert result.status_code==200,result.text
    identifier=result.json()['id']
    try:
        environment={key:value for key,value in os.environ.items() if key!='CZERO_TEST_GITHUB_TOKEN'}
        environment.update({'CZERO_DATABASE_URL':os.environ['CZERO_TEST_DATABASE_URL'],
            'CZERO_OIDC_ISSUER':identity['issuer'],'CZERO_OWNER_LDAP_UUID':str(identity['account_key']),
            'CZERO_SOURCE_DIR':str(live.originals.root)})
        token=os.getenv('CZERO_TEST_GITHUB_TOKEN')
        if token:
            credential=tmp_path/'github-token'
            descriptor=os.open(credential,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(descriptor,'w') as stream:stream.write(token)
            environment['CZERO_GITHUB_TOKEN_FILE']=str(credential)
        for _ in range(2):
            worker=subprocess.run([sys.executable,'-m','czero_app.worker'],env=environment,capture_output=True,text=True,timeout=130)
            assert worker.returncode==0,'Native source worker failed; keep its private diagnostics'
        runs=live.rest.get('/api/v1/automatic-sources/'+identifier+'/runs',params={'space_id':live.space}).json()['runs']
        assert runs[0]['state']=='complete',runs[0]['error_code']
        documents=live.rest.get('/api/v1/automatic-sources/'+identifier+'/documents',params={'space_id':live.space}).json()['documents']
        assert len(documents)==1
        document=live.rest.get('/api/v1/source-documents/'+documents[0]['id'],params={'space_id':live.space})
        assert document.status_code==200
        original=document.json()
        assert original['content_hash']==expected and original['state']=='ready'
        assert revision in original['metadata']['original_url']
        browser.goto(live.origin+'/sources/'+documents[0]['id']+'?'+urlencode({'space_id':live.space}))
        expect(browser.get_by_role('article')).to_contain_text('self-hosted knowledge service')
    finally:
        (tmp_path/'github-token').unlink(missing_ok=True)
        response=live.rest.post('/api/v1/automatic-sources/'+identifier+'/actions',params={'space_id':live.space},json={'action':'remove','expected_revision':1,'idempotency_key':'remove-pinned-public-readme'})
        assert response.status_code==200
        live.resume_worker()
