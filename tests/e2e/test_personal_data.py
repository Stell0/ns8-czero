# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Native browser cookies, CSRF and selected personal-space authority."""
from uuid import uuid4


def test_personal_reader_browser_selection_crud_and_isolation(live,browser):
    spaces=live.provision_personal()
    browser.goto(live.origin+'/?space_id='+spaces['member'])
    browser.get_by_role('button',name='Knowledge space Personal Data',exact=True).wait_for()
    def request(method,path,data=None,space=None):
        return browser.evaluate("""async ({method,path,data,space}) => {
          const me=await (await fetch('/api/v1/me')).json();
          const response=await fetch(path+(space?'?space_id='+space:''),{
            method, headers:{'Content-Type':'application/json','X-C0-CSRF':me.csrf_token},
            ...(data?{body:JSON.stringify(data)}:{})});
          return {status:response.status, data:response.status===204?null:await response.json()};
        }""",{'method':method,'path':path,'data':data,'space':space})
    assert request('GET','/api/v1/me')['data']['role']=='reader'
    assert request('GET','/api/v1/me',space=spaces['member'])['data']['role']=='editor'
    payload={'slug':'my-note','title':'Personal browser note','body':'My private knowledge','idempotency_key':uuid4().hex}
    created=request('POST','/api/v1/wiki/pages/upsert',payload,spaces['member'])
    assert created['status']==200
    row=created['data'];path='/api/v1/wiki/pages/'+row['id']
    assert request('GET',path,space=spaces['member'])['data']['content']['body']==payload['body']
    edited=request('PUT',path,{'title':row['title'],'body':'My correction','expected_revision':row['revision'],'idempotency_key':uuid4().hex},spaces['member'])
    assert edited['status']==200
    assert request('POST','/api/v1/wiki/pages/upsert',{**payload,'idempotency_key':uuid4().hex})['status']==403
    assert request('GET',path,space=spaces['other'])['status']==403
    assert request('PUT','/api/v1/spaces/'+spaces['member']+'/access',{'readable_by_all':True,'expected_revision':1,'idempotency_key':uuid4().hex})['status']==403
    removed=request('POST',path+'/archive',{'expected_revision':edited['data']['revision'],'idempotency_key':uuid4().hex},spaces['member'])
    assert removed['status']==200
    assert request('GET',path,space=spaces['member'])['data']['deleted'] is True


def test_personal_browser_key_write_and_admin_no_sharing(live,browser):
    from playwright.sync_api import expect
    spaces=live.provision_personal()
    browser.goto(live.origin+'/account')
    browser.get_by_role('button',name='Create API key',exact=True).click()
    dialog=browser.get_by_role('dialog')
    dialog.get_by_role('textbox',name='Name',exact=True).fill('Personal workflow')
    dialog.get_by_role('checkbox',name='Write',exact=True).check()
    expect(dialog.get_by_role('checkbox',name='Shared',exact=True)).to_be_disabled()
    dialog.get_by_role('checkbox',name='Personal Data',exact=True).check()
    dialog.get_by_role('button',name='Create API key',exact=True).click()
    secret=browser.get_by_role('textbox',name='Copy this key now. It will not be shown again.',exact=True).input_value()
    headers={'Authorization':'Bearer '+secret}
    assert live.rest.get('/api/v1/me',headers=headers).json()['role']=='reader'
    payload={'slug':'key-note','title':'Key note','body':'My personal knowledge','idempotency_key':uuid4().hex}
    assert live.rest.post('/api/v1/wiki/pages/upsert',params={'space_id':spaces['member']},headers=headers,json=payload).status_code==200
    assert live.rest.post('/api/v1/wiki/pages/upsert',headers=headers,json={**payload,'idempotency_key':uuid4().hex}).status_code==403
    browser.get_by_role('button',name='I saved the key',exact=True).click()
    browser.context.clear_cookies()
    browser.context.add_cookies([{'name':'fixture_persona','value':'owner','url':live.origin,'secure':True,'sameSite':'Lax'}])
    browser.goto(live.origin+'/auth/login')
    requests=[]
    browser.on('request',lambda request:requests.append(request.url))
    browser.goto(live.origin+'/admin/spaces?space_id='+spaces['member'])
    expect(browser.get_by_text('Personal Data spaces cannot be shared.',exact=True)).to_be_visible()
    expect(browser.get_by_role('button',name='Save audience',exact=True)).to_have_count(0)
    assert not any('/spaces/'+spaces['member']+'/grants' in path for path in requests)
