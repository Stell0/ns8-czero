# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Actual installed Vue workflows, using Robot's existing private browser session.

Knowledge fixtures use the public REST boundary. Reading never invokes those
helpers: the website deliberately has no knowledge authoring controls.
"""
import json
from pathlib import Path
import secrets
import shlex
import tempfile
from urllib.parse import urlencode, urlsplit


class NativeWebsite:
    def __init__(self, owner, host, builtin):
        self.owner, self.host, self.builtin = owner, host, builtin
        self.origin = 'https://' + host
        self.browser = builtin.get_library_instance('Browser')
        self.ssh = builtin.get_library_instance('SSHLibrary')
        self.password = json.loads(self.ssh.execute_command('cat /tmp/czero-oidc-fixture/personas.json'))['password']
        owner._browser_password = self.password

    def run(self, name, *args):
        return self.builtin.run_keyword('Browser.' + name, *args)

    def button(self, name, within=''):
        return (within.strip() + ' >> ' if within else '') + self.role('button', name)

    def role(self, kind, name):
        return 'role=' + kind + '[name=' + json.dumps(name) + ']'

    def click(self, name, within=''):
        self.run('Click', self.button(name, within))

    def dialog_closed(self):
        # Nebula's fixed panel leaves its role wrapper with no layout box.
        # Hidden therefore does not establish that an asynchronous save ended.
        self.run('Wait For Elements State','[role="dialog"]','detached','timeout=30s')

    def fill(self, name, value):
        self.browser.fill_text(self.role('textbox', name), value)

    def select(self, label, option):
        self.run('Click', 'role=button[name=/^' + label + '/]')
        self.run('Click', self.role('option', option))

    def checked(self, name, value=True):
        self.run('Check Checkbox' if value else 'Uncheck Checkbox', self.role('checkbox', name))

    def fresh(self):
        context = self.run('New Context', 'ignoreHTTPSErrors=True', 'acceptDownloads=True')
        self.run('New Page')
        return context

    def provider(self, username):
        self.run('Wait For Elements State', 'input[name="password"]', 'visible', 'timeout=30s')
        if self.browser.get_element_count('input[name="username"]:visible'):
            self.browser.fill_text('input[name="username"]', username)
        self.browser.fill_text('input[name="password"]', self.password)
        self.run('Click', '#kc-login')

    def login(self, username='c0owner', remember=False):
        self.run('Go To', self.origin + '/auth/sign-in')
        remember_control = self.role('checkbox', 'Remember this device')
        self.run('Get Property', remember_control, 'checked', '==', False)
        if remember:self.run('Check Checkbox', remember_control)
        self.click('Continue with NethServer')
        self.provider(username)
        self.run('Wait For Elements State', 'header:has-text("Knowledge space") button[aria-haspopup="listbox"], [name="accept"]', 'visible', 'timeout=30s')
        if self.browser.get_element_count('[name="accept"]'):self.run('Click', '[name="accept"]')
        self.signed()
        if remember:assert self.api('me')['browser_session']['remembered'] is True

    def signed(self):
        self.run('Wait For Elements State', 'role=button[name=/^Knowledge space /]', 'visible', 'timeout=30s')

    def goto(self, path):
        self.run('Go To', self.origin + path)
        self.signed()

    def api(self, path, data=None, method=None, status=200, space=None):
        """Test setup/assertion only; no website mutation control is synthesized."""
        url = '/api/v1/' + path
        if space:url += ('&' if '?' in url else '?') + urlencode({'space_id':space})
        payload = {'url':url, 'data':data, 'method':method or ('POST' if data is not None else 'GET')}
        code = '''async () => {
            const input=PAYLOAD, headers={};
            if(input.method!=='GET') {
              const me=await (await fetch('/api/v1/me',{cache:'no-store'})).json();
              headers['X-C0-CSRF']=me.csrf_token;
              if(input.data!==null)headers['Content-Type']='application/json';
            }
            const response=await fetch(input.url,{method:input.method,headers,cache:'no-store',body:input.data===null?undefined:JSON.stringify(input.data)});
            return {status:response.status,data:response.status===204?null:await response.json()};
        }'''.replace('PAYLOAD', json.dumps(payload))
        result = self.browser.evaluate_javascript(None, code)
        assert result['status'] == status, 'Native REST assertion failed: ' + path.split('?')[0] + ' (HTTP ' + str(result['status']) + ')'
        return result['data']

    def command(self, value, timeout='180 seconds'):
        _, _, rc = self.ssh.execute_command(value, return_stderr=True, return_rc=True, timeout=timeout)
        assert rc == 0, 'Native fixture command failed'

    def reader(self):
        self.command('python3 /tmp/oidc_probe.py browser-reader')
        self.fresh();self.login('c0member')

    def accessible(self, page, role):
        from CzeroSso import assert_accessibility
        assert_accessibility(self.browser, page, role)

    def read_only(self):
        self.run('Get Element Count', 'main form, main textarea:not([readonly])', '==', 0)
        self.run('Get Element Count', 'main >> role=button[name=/^(Save|Create|Edit|Delete|Archive|Annotate)/]', '==', 0)
        self.run('Get Element Count', 'main img, main iframe, main script', '==', 0)

    def account_switch(self, module_id):
        self.run('Go To', self.origin + '/auth/login');self.provider('c0denied')
        self.run('Get Text', 'main', 'contains', 'Access denied')
        self.run('Click', self.role('link','Sign in with another account'))
        self.run('Wait For Elements State', 'input[name="password"]', 'visible', 'timeout=30s')
        if self.browser.get_element_count('#reset-login'):self.run('Click','#reset-login')
        self.provider('c0owner');self.signed()
        self.goto('/account');self.run('Get Text','main','contains','c0owner')
        self.command('python3 /tmp/oidc_fixture.py check-logs '+shlex.quote(module_id))

    def objects(self):
        self.login(remember=True)
        type_name='browser-inventory-'+secrets.token_hex(4)
        self.api('object-types',{'name':type_name,'label':'Browser inventory','schema':{'type':'object','properties':{'name':{'type':'string','maxLength':64},'count':{'type':'integer','minimum':0}},'required':['name','count']},'unique_fields':['name']},status=201)
        self.api('objects',{'type_name':type_name,'data':{'name':3,'count':2}},status=422)
        record=self.api('objects',{'type_name':type_name,'data':{'name':'Browser rack','count':2},'tags':['inventory','priority']},status=201)
        hostile='<img src=x onerror=alert(1)>'
        updated=self.api('objects/'+record['id'],{'data':{'name':hostile,'count':3},'expected_revision':record['revision']},'PUT')
        assert updated['revision']==2
        self.api('objects/'+record['id'],{'data':{'name':'stale','count':0},'expected_revision':1},'PUT',status=409)
        target=self.api('objects',{'type_name':type_name,'data':{'name':'Browser linked target','count':4}},status=201)
        self.api('object-relations',{'source_id':record['id'],'target_id':target['id'],'source_type':type_name,'target_type':type_name,'kind':'related-to'},status=201)
        for role in ('admin','reader'):
            if role=='reader':self.reader()
            self.goto('/explore/records?'+urlencode({'type':type_name}))
            self.run('Click',self.role('link',hostile))
            self.run('Get Text','main','contains',hostile)
            self.run('Get Text','main','contains','related-to')
            self.read_only();self.accessible('records',role)
            self.run('Click','main a:has-text("related-to")')
            self.run('Get Text','main','contains','Browser linked target')
            self.read_only()

    def upload(self, path, title, replacement=False, retain=False):
        self.click('Upload replacement' if replacement else 'Upload source')
        dialog='[role="dialog"] '
        self.run('Get Property',self.role('checkbox','Retain the original file'),'checked','==',False)
        if not replacement:self.fill('Title',title)
        self.run('Upload File By Selector',dialog+'input[type=file]',str(path))
        if retain:self.checked('Retain the original file')
        self.click('Upload replacement' if replacement else 'Upload source',dialog)
        self.dialog_closed()

    def extracted(self, selector, text):
        # Native extraction retains the pre-cutover 100-second worker deadline.
        self.builtin.run_keyword('Wait Until Keyword Succeeds','100s','1s',
            'Browser.Get Text',selector,'contains',text)

    def sources(self):
        self.login();self.goto('/sources')
        self.accessible('sources','admin')
        title='<img src=x onerror=alert(1)> browser-source-'+secrets.token_hex(4)
        sample=Path(__file__).parent/'fixtures/evidence/sample.txt'
        self.upload(sample,title,retain=True)
        self.extracted('[role="article"]',sample.read_text())
        self.run('Get Element Count','main img','==',0)
        source_id=urlsplit(self.browser.get_url()).path.rsplit('/',1)[1]
        before=self.api('source-documents/'+source_id)
        chunk=self.api('documents/'+before['parts'][0]['document_id']+'/chunks')['chunks'][0]
        self.upload(sample,title,replacement=True,retain=True)
        assert len(self.api('sources/'+source_id+'/versions')['versions'])==1
        with tempfile.TemporaryDirectory(prefix='c0-native-source-') as directory:
            changed=Path(directory)/'changed.txt';changed.write_text('Browser revised evidence inventory\n')
            self.upload(changed,title,replacement=True,retain=True)
            self.extracted('[role="article"]','Browser revised evidence')
            assert self.api('sources/'+source_id)['revision']==2
            self.api('chunks/'+chunk['id']+'/citation',status=410)
            invalid=Path(directory)/'invalid.txt';invalid.write_bytes(b'\xff\xfeinvalid')
            self.goto('/sources');self.upload(invalid,'Browser quarantined evidence')
            failed_id=urlsplit(self.browser.get_url()).path.rsplit('/',1)[1]
            self.extracted('main div[role=status]','Failed')
            self.run('Get Element Count','[role="article"]','==',0)
            self.click('Retry processing')
            self.run('Wait For Elements State',self.button('Retry processing'),'enabled','timeout=100s')
            self.extracted('main div[role=status]','Failed')
        self.reader();self.goto('/sources/'+source_id)
        self.run('Get Text','[role="article"]','contains','Browser revised evidence')
        self.run('Get Element Count',self.button('Upload replacement'),'==',0)
        current=self.api('source-documents/'+source_id)
        chunk=self.api('documents/'+current['parts'][0]['document_id']+'/chunks')['chunks'][0]
        self.goto('/evidence/'+chunk['id'])
        self.run('Get Text','[role="article"]','contains','Browser revised evidence')
        self.run('Click','summary:text-is("Evidence")')
        self.run('Get Text','details[open]','contains',chunk['id'])
        self.accessible('sources','reader')
        self.goto('/sources/'+failed_id)
        self.extracted('main div[role=status]','Failed')
        self.run('Get Element Count','[role="article"], main a:has-text("Download original")','==',0)
        self.run('Get Element Count',self.button('Retry processing','main'),'==',0)
        self.fresh();self.login();self.api('sources/'+source_id+'?expected_revision=2',method='DELETE')
        assert not self.api('sources/search?'+urlencode({'query':'"Browser revised evidence"'}))['citations']
        self.goto('/sources?'+urlencode({'query':'"Browser revised evidence"'}))
        self.run('Get Text','main','contains','No items found')

    def create_wiki_fixture(self):
        slug='browser-wiki/article-'+secrets.token_hex(4);title='<img src=x onerror=alert(1)> '+slug
        retry_key=slug.replace('/',':')
        page=self.api('wiki/pages',{'slug':slug,'title':title,'body':'# Authored browser content','metadata':{'fixture':'browser'},'idempotency_key':retry_key},status=201)
        revised=self.api('wiki/pages/'+page['id'],{'title':title,'body':'# Revised browser content','metadata':page['content']['metadata'],'expected_revision':page['revision'],'idempotency_key':retry_key+'-update'},'PUT')
        assert revised['revision']==2
        return revised

    def wiki(self):
        self.login()
        expected=json.loads(self.ssh.execute_command('cat /tmp/czero-oidc-fixture/expected-identities.json'))['knowledge']
        page=self.create_wiki_fixture();title=page['title']
        for role in ('admin','reader'):
            if role=='reader':self.reader()
            self.goto('/wiki/'+page['id'])
            self.run('Get Text','main','contains',title)
            self.run('Get Text','article','contains','Revised browser content')
            self.read_only();self.accessible('wiki',role)
            self.api('wiki/pages/'+page['id']+'?revision=1',status=410)
            self.goto('/explore/entities/'+expected['entities'][0]['id'])
            self.run('Get Text','main','contains','Linked facts')
            self.read_only()
            for claim in expected['claims']:
                self.goto('/explore/claims/'+claim['id'])
                self.run('Wait For Elements State','main a[href*="/evidence/"]','visible','timeout=30s')
                self.read_only()

    def search_details(self, method):
        selector='main details:has(> summary:text-is("Search details")):has(> p:has-text('+json.dumps(method+' ·',ensure_ascii=False)+'))'
        self.run('Wait For Elements State',selector,'attached','timeout=30s')
        if not self.browser.get_property(selector,'open'):
            self.run('Click',selector+' > summary')
        self.run('Get Text',selector,'contains',method)

    def search(self):
        page=json.loads(self.ssh.execute_command('cat /tmp/czero-oidc-fixture/expected-identities.json'))['knowledge']['page']
        result='main >> '+self.role('link',page['title'])
        for username,role in [('c0owner','admin'),('c0member','reader')]:
            if role=='reader':self.fresh()
            self.login(username);self.goto('/search')
            self.accessible('search',role)
            self.fill('Search knowledge','independent authored')
            self.click('Search','header ')
            self.run('Click','summary:text-is("Advanced search")')
            self.select('Retrieval','Hybrid');self.select('Scoring','Filter if allowed')
            self.search_details('hybrid+filter')
            self.run('Get Element Count',result,'==',1)
            self.select('Retrieval','Text');self.select('Scoring','Off')
            self.search_details('text')
            self.run('Click',result)
            self.run('Wait For Elements State','article','visible','timeout=30s')
            self.run('Get Text','article','contains','Independent authored claims')
            self.read_only()
            self.run('Go Back')
            self.run('Get Property',self.role('textbox','Search knowledge'),'value','==','independent authored')

    def permissions(self, account, choice):
        row='[data-account-id="'+account+'"] '
        self.click('Change permissions',row)
        self.select('Permission',choice)
        self.click('Save','[role="dialog"] ')
        self.dialog_closed()

    def grant(self, choice):
        row='main li:has(button[aria-labelledby]):has-text("c0member") '
        self.select('c0member',choice)
        self.click('Save access',row)
        # The actual post-save readback must settle before another revision.
        self.run('Wait For Elements State',self.button('Save access',row),'enabled','timeout=30s')

    def spaces(self, module_id):
        owner_context=self.fresh();self.login()
        member=next(row for row in self.api('access/accounts')['accounts'] if row['username']=='c0member')
        self.goto('/admin');self.permissions(member['id'],'Read and write')
        self.goto('/admin/spaces')
        name='<img src=x> protected-'+secrets.token_hex(4)
        self.fill('Name',name);self.click('Create space')
        self.run('Wait For Elements State','header button:has-text('+json.dumps(name)+')','visible','timeout=30s')
        from urllib.parse import parse_qs
        space=parse_qs(urlsplit(self.browser.get_url()).query)['space_id'][0]
        self.run('Get Element Count','main img, header img','==',0)
        self.grant('Read');self.accessible('admin','admin')
        page=self.api('wiki/pages',{'slug':'private/'+secrets.token_hex(4),'title':'Private browser article','body':'# Private original','idempotency_key':'native-private-page'},status=201,space=space)
        self.api('wiki/pages/'+page['id'],{'title':page['title'],'body':'# Private revised','metadata':{},'expected_revision':1,'idempotency_key':'native-private-update'},'PUT',space=space)
        self.goto('/projects?space_id='+space)
        probe=Path(__file__).with_name('project_browser_probe.js').read_text()
        assert self.browser.evaluate_javascript(None,'('+probe+')')=={'initialized':True,'replay':True,'revision':2,'workflows':True,'monitoring':True,'reports':True}
        self.run('Reload')
        for text in ('<img src=x> Synthetic research','<script> synthetic topic','browser-source','partial','<script> synthetic queued investigation','phase_incomplete','no_material_update'):
            self.run('Get Text','main','contains',text)
        self.run('Wait For Elements State','main a[href*="/wiki/"][href*="revision=1"]','visible','timeout=30s')
        href=self.browser.get_attribute('main a[href*="/wiki/"][href*="revision=1"]','href')
        assert 'space_id='+space in href
        self.read_only();self.accessible('projects','admin')
        member_context=self.fresh();self.login('c0member')
        article='/wiki/'+page['id']+'?space_id='+space
        self.goto(article);self.run('Get Text','article','contains','Private revised')
        self.read_only();self.accessible('wiki','reader')
        self.api('wiki/pages/'+page['id'],{'title':page['title'],'body':'Denied','metadata':{},'expected_revision':2,'idempotency_key':'native-reader-denied'},'PUT',status=403,space=space)
        retained=json.loads(self.ssh.execute_command('cat /tmp/czero-oidc-fixture/expected-identities.json'))['protected']
        citation=retained['sources'][0]['citation']
        self.goto('/evidence/'+citation['chunk_id']+'?space_id='+retained['space']['id'])
        self.run('Get Text','role=article','contains','Selected native memory evidence');self.accessible('sources','reader')
        self.run('Switch Context',owner_context);self.goto('/admin/spaces?space_id='+space);self.grant('Read and write')
        self.run('Switch Context',member_context);self.goto(article)
        self.api('wiki/pages/'+page['id'],{'title':page['title'],'body':'# Independent private update','metadata':{},'expected_revision':2,'idempotency_key':'native-editor-update'},'PUT',space=space)
        self.run('Reload');self.run('Get Text','article','contains','Independent private update')
        self.read_only();self.accessible('wiki','editor')
        self.command('runagent -m '+shlex.quote(module_id)+' systemctl --user restart czero-pod.service')
        self.builtin.run_keyword('Wait Until Keyword Succeeds','30s','2s','Check application route')
        self.goto('/projects?space_id='+space)
        self.run('Get Text','main','contains','Configuration 2');self.run('Get Text','main','contains','no_material_update')
        self.goto(article);self.run('Get Text','article','contains','Independent private update')
        self.api('wiki/pages/'+page['id']+'?revision=1',status=410,space=space)
        self.run('Switch Context',owner_context);self.goto('/admin/spaces?space_id='+space);self.grant('No additional grant')
        self.run('Switch Context',member_context)
        self.browser.evaluate_javascript(None,"() => document.dispatchEvent(new Event('visibilitychange'))")
        self.run('Get Text','main','contains','Sign in or choose a space you can access.')
        self.run('Get Element Count','article, main a[download]','==',0)
        assert 'space_id='+space in self.browser.get_url()
        self.run('Reload');self.run('Get Element Count','article','==',0)
        self.run('Go To',self.origin+'/projects?space_id='+space)
        self.run('Get Text','main','contains','Sign in or choose a space you can access.')
        self.run('Get Element Count','main li','==',0)

    def discovery(self, module_id):
        output, rc = self.ssh.execute_command('api-cli run module/'+shlex.quote(module_id)+'/get-configuration', return_rc=True, timeout='180 seconds')
        assert rc == 0 and 'cimd_enabled' not in json.loads(output)

    def people_access(self, module_id):
        from workspace_access_evidence import validate_measurement, require_stages
        measurements=[]
        def phase(name):
            output,_,rc=self.ssh.execute_command('python3 /tmp/access_fixture.py '+shlex.quote(module_id)+' '+name,return_stderr=True,return_rc=True,timeout='180 seconds')
            assert rc==0,'Native access fixture failed at '+name
            marker='C0 workspace access: '
            lines=[line for line in output.splitlines() if line.startswith(marker)]
            assert len(lines)==1
            measured=validate_measurement(json.loads(lines[0][len(marker):]));assert measured['phase']==name
            measurements.append(measured);self.builtin.log_to_console(marker+json.dumps(measured,sort_keys=True))
        output,rc=self.ssh.execute_command('api-cli run module/'+shlex.quote(module_id)+'/get-configuration',return_rc=True,timeout='180 seconds')
        assert rc==0
        assert 'cimd_enabled' not in json.loads(output)
        try:
            self.discovery(module_id);phase('prepare')
            self.run('Reload')
            value=json.loads(self.ssh.execute_command('cat /tmp/czero-oidc-fixture/workspace-access.json'))
            row='[data-application-id="'+value['request_id']+'"] '
            self.click('Approve application',row)
            self.run('Get Text','[role="dialog"]','contains','C0 disposable access browser')
            for name in ('Write','Manage'):self.run('Get Property',self.role('checkbox',name),'checked','==',False)
            self.run('Get Property',self.role('checkbox','Read'),'checked','==',False)
            self.checked('Write',True)
            self.click('Approve application','[role="dialog"] ')
            self.dialog_closed();phase('approved')
            self.click('Reload')
            sibling='[data-application-id]:not([data-application-id="'+value['request_id']+'"]) '
            self.click('Decline application',sibling);self.click('Decline application','[role="dialog"] ')
            self.dialog_closed();phase('declined')
            value=json.loads(self.ssh.execute_command('cat /tmp/czero-oidc-fixture/workspace-access.json'))
            self.click('Reload');row='[data-application-id="'+value['connection_ids'][0]+'"] '
            self.click('Disconnect',row);self.click('Disconnect','[role="dialog"] ')
            self.dialog_closed();phase('disconnected')
            self.permissions(value['member_id'],'Block access');phase('blocked')
            self.command('api-cli run node/1/restart-module --data '+shlex.quote(json.dumps({'module_id':module_id})))
            self.builtin.run_keyword('Wait Until Keyword Succeeds','30s','2s','Check application route');phase('blocked_after_restart')
            self.run('Reload');self.permissions(value['member_id'],'Read');phase('unblocked')
            for option,stage in [('Read and write','editor_permissions'),('Read, write and manage','manage_permissions'),('Read','reader_permissions')]:
                self.permissions(value['member_id'],option);phase(stage)
            require_stages(measurements);self.accessible('admin','admin')
        finally:self.discovery(module_id)

    def skip(self):
        before=urlsplit(self.browser.get_url())
        self.run('Press Keys','body','Tab')
        self.run('Wait For Elements State','.skip-link','focused')
        self.run('Press Keys','.skip-link','Enter')
        self.run('Wait For Elements State','main','focused')
        assert before._replace(fragment='')==urlsplit(self.browser.get_url())._replace(fragment=''), 'Skip link changed page or selected space'

    def admin(self, role, module_id):
        self.goto('/admin')
        if role!='admin':
            self.run('Get Text','main','contains','Sign in or choose a space you can access.')
            self.run('Get Element Count','[role="grid"], aside a:text-is("Administration")','==',0)
            self.accessible('admin',role)
            return
        self.run('Wait For Elements State','[role="grid"]','visible','timeout=30s')
        self.accessible('admin',role);self.people_access(module_id)
        self.goto('/admin/advanced');self.skip()
        output,rc=self.ssh.execute_command('api-cli run module/'+shlex.quote(module_id)+'/get-configuration',return_rc=True,timeout='180 seconds')
        assert rc==0;assert 'cimd_enabled' not in json.loads(output)
        try:
            self.discovery(module_id);self.run('Reload');self.click('Register client')
            self.select('Clients','HTTPS')
            for url in ('https://127.0.0.1/client.json','https://localhost/client.json'):
                self.fill('Client metadata URL',url);self.click('Load application','[role="dialog"] ')
                self.run('Wait For Elements State','[role="dialog"] [role="alert"]','visible','timeout=30s')
                self.run('Wait For Elements State',self.button('Approve application','[role="dialog"] '),'disabled')
            self.run('Click',self.role('button','Close'))
        finally:self.discovery(module_id)
        self.run('Reload');self.click('Register client')
        name='browser-client-'+secrets.token_hex(4)
        self.fill('Name',name);self.fill('Callback','https://client.example.test/callback')
        self.click('Approve application','[role="dialog"] ')
        row='main li:has(h2:text-is('+json.dumps(name)+')) '
        self.click('Disable',row)
        self.run('Wait For Elements State',self.button('Enable',row),'visible','timeout=30s')
        self.goto('/admin/work');self.skip();self.click('Queue job')
        self.select('Handler','health');self.fill('Parameters (JSON)','{}')
        self.click('Queue job','[role="dialog"] ')
        self.dialog_closed()
        job=next(item for item in self.api('jobs')['jobs'] if item['handler']=='health')
        for _ in range(45):
            if self.api('jobs/'+job['id'])['state']=='succeeded':break
            self.builtin.run_keyword('Sleep','2s')
        assert self.api('jobs/'+job['id'])['state']=='succeeded'
        self.click('Reload');self.click('Details','main li:has-text('+json.dumps(job['id'])+') ')
        self.run('Get Text','main pre','contains','succeeded')
        self.select('Background work','Schedules');self.click('Create schedule')
        name='browser-schedule-'+secrets.token_hex(4)
        self.fill('Name',name);self.select('Handler','health')
        self.fill('Parameters (JSON)','{}');self.fill('Interval in seconds','3600')
        self.click('Create schedule','[role="dialog"] ')
        self.dialog_closed()
        row='main li:has-text('+json.dumps(name)+') '
        self.click('Details',row);self.checked('Enabled',False)
        self.fill('Interval in seconds','7200');self.click('Save')
        self.run('Get Text',row,'contains','7200')
        self.run('Reload');self.select('Background work','Schedules');self.click('Details',row)
        self.run('Get Property',self.role('checkbox','Enabled'),'checked','==',False)
        self.run('Get Property',self.role('textbox','Interval in seconds'),'value','==','7200')
        self.accessible('admin',role)

    def key_status(self, secret):
        # Keep the one-time secret out of Robot keyword arguments and logs.
        check='async () => (await fetch("/api/v1/me", {credentials:"omit",cache:"no-store",headers:{Authorization:"Bearer "+'+json.dumps(secret)+'}})).status'
        return self.browser.evaluate_javascript(None,check)

    def keys(self, role):
        name='Native disposable key '+secrets.token_hex(4)
        row='main li:has-text('+json.dumps(name)+') '
        self.click('Create API key');self.fill('Name',name)
        self.checked('Shared');self.click('Create API key','[role="dialog"] ')
        secret_control=self.role('textbox','Copy this key now. It will not be shown again.')
        self.run('Wait For Elements State',secret_control,'visible','timeout=30s')
        secret=self.browser.get_property(secret_control,'value');assert secret.startswith('c0k_')
        self.click('I saved the key')
        self.run('Get Element Count',secret_control,'==',0)
        self.run('Wait For Elements State',self.button('Revoke API key',row),'visible','timeout=30s')
        self.accessible('account',role)
        status=self.key_status(secret);assert status==200,'Created key returned HTTP '+str(status)
        self.click('Revoke API key',row);self.click('Revoke API key','[role="dialog"] ')
        self.dialog_closed()
        self.run('Wait For Elements State',self.button('Revoke API key',row),'hidden','timeout=30s')
        saved=next(item for item in self.api('api-keys')['api_keys'] if item['name']==name)
        assert saved['revoked_at'],'Selected key revocation was not saved'
        status=self.key_status(secret)
        self.builtin.log_to_console('C0 key revocation: '+json.dumps({'role':role,'saved':True,'http_status':status}))
        assert status==401,'Revoked key returned HTTP '+str(status)
        secret=None

    def oauth(self, module_id):
        for role in ('admin','reader','editor'):
            command='python3 /tmp/oauth_fixture.py '+shlex.quote(module_id)
            self.command(command+' browser-prepare '+role)
            value=json.loads(self.ssh.execute_command('cat /tmp/czero-oidc-fixture/browser-oauth.json'))
            self.fresh()
            if role=='admin':self.login(remember=True)
            self.browser.go_to(value['authorization_url'])
            if role!='admin':self.provider('c0member')
            self.run('Wait For Elements State',self.button('Authorize'),'enabled','timeout=30s')
            self.run('Get Text','main h2','==',value['client']['client_name'])
            self.run('Get Element Count','main img','==',0)
            disabled={'admin':0,'editor':1,'reader':2}[role]
            self.run('Get Element Count','main fieldset input:disabled','==',disabled)
            self.run('Get Element Count','main fieldset input:checked','==',3-disabled)
            self.run('Get Property',self.role('checkbox','Allow background access'),'checked','==',False)
            self.run('Get Text','main','contains','30 days')
            if role=='admin':
                self.checked('Allow background access');self.click('Continue to background sign-in')
                self.provider('c0owner')
                self.run('Wait For Elements State','main button:has-text("Authorize"), [name="accept"]','visible','timeout=30s')
                if self.browser.get_element_count('[name="accept"]'):self.run('Click','[name="accept"]')
                self.run('Wait For Elements State',self.button('Authorize'),'enabled','timeout=30s')
                self.run('Get Property',self.role('checkbox','Allow background access'),'checked','==',True)
                value['persistent']=True
            self.click('Authorize');self.run('Get Text','h1','==','Use with AI')
            self.run('Get Property',self.role('textbox','MCP server URL'),'value','==',self.origin+'/mcp')
            with tempfile.TemporaryDirectory(prefix='czero-agent-download-') as directory:
                path=Path(directory)/'memory.skill'
                promise=self.browser.promise_to_wait_for_download(saveAs=str(path))
                self.run('Click',self.role('link','Download skill'));self.browser.wait_for(promise)
                self.owner._verify_agent_archive(path,self.host)
                self.fill('Registered ChatGPT app ID','asdk_app_disposable')
                path=Path(directory)/'plugin.zip'
                promise=self.browser.promise_to_wait_for_download(saveAs=str(path))
                self.click('Download ChatGPT plugin');self.browser.wait_for(promise)
                self.owner._verify_agent_archive(path,self.host,plugin=True)
            value['returned_callback']=self.browser.get_url()
            with tempfile.TemporaryDirectory(prefix='czero-oauth-browser-') as directory:
                path=Path(directory)/'request.json';path.write_text(json.dumps(value));path.chmod(0o600)
                self.ssh.put_file(str(path),'/tmp/czero-oidc-fixture/browser-oauth.json',mode='0600')
            self.command(command+' browser-complete',timeout='300 seconds')
            self.goto('/account')
            if role=='admin':assert self.api('me')['browser_session']['remembered'] is True
            row='main li:has(h3:text-is('+json.dumps(value['client']['client_name'])+')) '
            self.accessible('account',role);self.click('Disconnect',row)
            self.click('Disconnect','[role="dialog"] ')
            self.run('Wait For Elements State',row,'hidden','timeout=30s')
            self.command(command+' browser-disconnected',timeout='60 seconds')
            self.keys(role)
            self.goto('/');self.accessible('home',role)
            self.goto('/agents')
            self.run('Get Element Count','details[data-task]','==',1 if role=='reader' else 7)
            expected={'research','structured-research','selective-context','cross-space-navigation'}
            if role!='reader':expected|={'knowledge-compiler','evidence','update','investigation','consolidate'}
            self.run('Get Element Count','details[data-workflow]','==',len(expected))
            actual=self.browser.evaluate_javascript(None,
                '() => Array.from(document.querySelectorAll("details[data-workflow]"), node => node.dataset.workflow)')
            assert set(actual)==expected, 'Unexpected authorized navigation workflows'
            self.run('Click','details[data-workflow="cross-space-navigation"] summary')
            self.run('Get Text','details[data-workflow="cross-space-navigation"]','contains','explicitly authorized publication task and destination')
            self.run('Get Text','details[data-workflow="cross-space-navigation"]','contains','independently authorized API')
            self.run('Get Element Count','details[data-workflow="knowledge-compiler"]','==',0 if role=='reader' else 1)
            if role!='reader':
                self.run('Click','details[data-workflow="knowledge-compiler"] summary')
                self.run('Get Text','details[data-workflow="knowledge-compiler"]','contains','enabled policy')
                self.run('Get Text','details[data-workflow="knowledge-compiler"]','contains','compilation_verify')
            self.run('Click','details[data-workflow="selective-context"] summary')
            self.run('Get Text','details[data-workflow="selective-context"]','contains','max_tokens is a bytes/3 estimate')
            if role!='reader':
                self.run('Click','details[data-workflow="consolidate"] summary')
                self.run('Get Text','details[data-workflow="consolidate"]','contains','superseded result returns content_superseded (410)')
            self.accessible('agents',role);self.admin(role,module_id)
            self.command(command+' browser-cleanup');self.run('Close Context')
        self.command('python3 /tmp/oidc_fixture.py check-logs '+shlex.quote(module_id))
