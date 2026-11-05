# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Real HTTPS/OAuth/worker acceptance for plain-question evidence retrieval."""
import time
from urllib.parse import urlencode

from playwright.sync_api import expect

from c0_ingest.auth import stored, store_path
from c0_ingest.state import atomic


def test_disposable_https_oauth_renewal_keeps_exact_identity(live):
    before=stored(live.client.config)
    # Only this disposable store is expired; the real token endpoint rotates it.
    atomic(store_path(live.client.config), {**before,'expires_at':time.time()-1})
    profile=live.client.call('get_profile')
    after=stored(live.client.config)
    assert profile['id']==live.client.profile['id']
    assert after['refresh_token']!=before['refresh_token']
    assert after['scope']==before['scope']
    assert not store_path(live.client.config).with_suffix('.json.pending').exists()


def test_question_search_opens_complete_current_document_and_loses_access(live,browser):
    body=('# Scheduled backup\n\nEnable scheduled backup in Example Mail 8 from the dashboard.\n\n'
          '| Port | Purpose |\n| --- | --- |\n| 443 | HTTPS |\n\n'
          '```python\nif ready:\n    backup()\n```\n\n'
          + '\n\n'.join('Recorded procedure paragraph '+str(i)+': retain the complete instructions.' for i in range(350))
          + '\n\nEND-COMPLETE-PROCEDURE\n')
    version=live.upload(body,title='Complete mail backup manual')
    query='How can I enable scheduled backup in Example Mail 8?'
    result=live.client.call('knowledge_search',options={'query':query,'mode':'text','rerank':'off','kind':'source'})
    assert result['lexical_strategy']=='relaxed' and result['retrieval_method']=='text'
    citation=result['hits'][0]['citation']
    browser.goto(live.origin+'/search?'+urlencode({'space_id':live.space}))
    browser.get_by_role('search').get_by_role('textbox').fill(query)
    browser.get_by_role('search').get_by_role('button',name='Search',exact=True).click()
    browser.locator('main').get_by_role('link',name='Complete mail backup manual',exact=True).first.click()
    expect(browser.get_by_role('article')).not_to_have_attribute('aria-busy','true',timeout=20000)
    document=browser.get_by_role('article')
    expect(document.locator('table')).to_contain_text('443')
    assert document.locator('pre code').text_content()=='if ready:\n    backup()\n'
    expect(document).to_contain_text('END-COMPLETE-PROCEDURE')
    browser.get_by_text('Provenance',exact=True).click()
    expect(browser.locator('details[open]')).to_contain_text('Synthetic product')
    replacement=body.replace('Enable scheduled backup','Configure manual retention').replace('END-COMPLETE-PROCEDURE','END-CURRENT-PROCEDURE')
    current=live.client.call('sources_get',source_id=version['source_id'])
    changed=live.upload(replacement,title='Complete mail backup manual',source_id=version['source_id'],expected_revision=str(current['revision']))
    assert changed['id']!=version['id']
    expired=live.rest.get('/api/v1/chunks/'+citation['chunk_id']+'/citation',params={'space_id':live.space})
    assert expired.status_code==410 and expired.json()['detail']=='content_superseded'
    browser.goto(live.origin+'/sources/'+version['source_id']+'?'+urlencode({'space_id':live.space}))
    expect(document).to_contain_text('END-CURRENT-PROCEDURE',timeout=20000)
    expect(document).not_to_contain_text('END-COMPLETE-PROCEDURE')
    assert live.rest.put(live.grant_path,json={'role':None,'expected_revision':1,'idempotency_key':'question-revoke'}).status_code==200
    browser.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
    expect(browser.get_by_text('Sign in or choose a space you can access.',exact=True)).to_be_visible()
    expect(document).to_have_count(0)
