# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
import base64
import json
import pytest
import httpx2

from czero_app.personal_data.connectors import NethVoice, ReadClient, Unavailable, WebTop
from czero_core.personal_text import html_text


def mail_transport(handle):
    def authenticated(request):
        if request.url.path=='/me/identities':
            return httpx2.Response(200,json=[{'isMain':True,'email':'alice@example.test'}])
        return handle(request)
    return httpx2.MockTransport(authenticated)


def token(name):
    return 'header.'+base64.urlsafe_b64encode(json.dumps({'id':name}).encode()).decode().rstrip('=')+'.signature'


def test_nethvoice_participation_ids_and_supervisor_exclusion():
    requests=[]
    def handle(request):
        requests.append(request)
        if request.url.path=='/user/me':
            return httpx2.Response(200,json={'username':'alice','endpoints':{'extension':[{'id':'201'}]}})
        if request.url.path=='/history/calls':
            assert request.url.params['callType']=='user'
            return httpx2.Response(200,json={'count':1,'rows':[{'uniqueid':'same','linkedid':'transfer'}]})
        if request.url.path=='/history/statuses':
            assert json.loads(request.content)['switchboard'] is False
            return httpx2.Response(200,json={'code':200,'data':[
                {'id':1,'uniqueid':'same','src_number':'201','dst_number':'202','state':'done','has_transcription':True},
                {'id':2,'uniqueid':'same','src_number':'202','dst_number':'203','state':'done','has_transcription':True},
                {'uniqueid':'same','src_number':'201','dst_number':'202','state':'done','has_transcription':True}]})
        assert request.url.path=='/transcripts/same'
        assert request.url.params['id']=='1'
        return httpx2.Response(200,json={'code':200,'data':{'src':'201','dst':'202','transcription':'Participated call'}})
    adapter=NethVoice('https://voice.example.test',token=token('alice'),username='alice',phone_numbers=['201'],transport=mail_transport(handle))
    docs,status=adapter.page(start='20200101',end='20261115')
    assert len(docs)==1 and docs[0].remote_key=='1' and docs[0].content==b'Participated call'
    assert status['skipped']==2 and not status['deletion_authoritative']
    assert all(r.method=='GET' or r.url.path=='/history/statuses' for r in requests)


@pytest.mark.parametrize('status',[401,403,500,503])
def test_session_errors_are_never_empty_successful_inventory(status):
    adapter=NethVoice('https://voice.example.test',token=token('alice'),username='alice',phone_numbers=['201'],
        transport=mail_transport(lambda r:httpx2.Response(status)))
    with pytest.raises(Unavailable) as error:adapter.page(start='20200101',end='20261115')
    assert error.value.code==('session_unavailable' if status in (401,403) else 'source_unavailable')


def test_wrong_token_identity_and_missing_session_fail_closed():
    with pytest.raises(Unavailable):NethVoice('https://voice.example.test',token=token('bob'),username='alice',phone_numbers=['201'])
    with pytest.raises(Unavailable):NethVoice('https://voice.example.test',token='',username='alice',phone_numbers=['201'])


def test_mail_reads_content_each_time_and_leaves_seen_unchanged():
    calls=[];body=['<p>First</p>','<p>Reused UID</p>']
    def handle(request):
        calls.append(request)
        assert request.method=='GET'
        assert request.headers['X-Auth-Username']=='alice@example.test'
        if request.url.path=='/me/messages/list':return httpx2.Response(200,json=[{'uid':42}])
        assert request.url.params['set_seen']=='false'
        return httpx2.Response(200,json={'uid':42,'body':body.pop(0),'attachments':[]})
    adapter=WebTop('https://mail.example.test',api_key='dedicated-key',username='alice@example.test',transport=mail_transport(handle))
    first,_=adapter.page('INBOX');second,status=adapter.page('INBOX')
    assert first[0].remote_key!=second[0].remote_key  # missing Message-ID: content change is a new uncertain generation
    assert first[0].content!=second[0].content
    assert first[0].metadata['webtop_response_hash']!=second[0].metadata['webtop_response_hash']
    assert not status['deletion_authoritative']
    assert len(calls)==4


def test_mail_folders_exclude_shared_and_excluded_ancestors():
    rows=[{'id':'INBOX','type':'inbox'}, {'id':'Trash','type':'trash','hasChildren':True},
          {'id':'Shared','type':'shared','hasChildren':True},{'id':'Public','type':'other','hasChildren':True},
          {'id':'Public/team/INBOX','type':'inbox'},{'id':'Shared/person/INBOX','type':'inbox'},
          {'id':'unknown'}, {'id':'Inbox/Junk/child','type':'other'}]
    adapter=WebTop('https://mail.example.test',api_key='dedicated-key',username='alice@example.test',
        transport=mail_transport(lambda r:httpx2.Response(200,json=rows)))
    assert [r['id'] for r in adapter.folders()]==['INBOX']


def test_html_extraction_never_fetches_or_renders_active_content():
    assert html_text('<head><title>hidden</title></head><p>Hello &amp; world</p><img src="https://evil.test/a"><script>secret()</script><p>End</p>')=='Hello & world\nEnd'


def test_read_client_refuses_writes_redirects_and_tool_errors():
    client=ReadClient('https://mail.example.test',{},transport=mail_transport(lambda r:httpx2.Response(200,json={'success':False})))
    with pytest.raises(ValueError):client.read('/me/messages/send',body={})
    with pytest.raises(ValueError):client.read('/me/messages',body={})
    with pytest.raises(Unavailable):client.read('/me/messages')
    redirect=ReadClient('https://mail.example.test',{},transport=mail_transport(lambda r:httpx2.Response(302,headers={'location':'https://evil.test'})))
    with pytest.raises(Unavailable):redirect.read('/me/messages')


def test_webtop_signed_java_uid_is_recovered_as_unsigned_imap_uid():
    def handle(request):
        if request.url.path=='/me/messages/list':return httpx2.Response(200,json=[{'uid':-1}])
        assert request.url.params['uid']=='4294967295'
        return httpx2.Response(200,json={'uid':-1,'id':'same-id@example.test','subject':'UID boundary','body':'<p>Message</p>','attachments':[]})
    source=WebTop('https://mail.example.test',api_key='dedicated-key',username='alice@example.test',transport=mail_transport(handle))
    docs,_=source.page('INBOX')
    assert docs[0].metadata['uid']==4294967295


def test_webtop_message_id_is_not_unique_across_folder_uid_slots():
    def handle(request):
        if request.url.path=='/me/messages/list':return httpx2.Response(200,json=[{'uid':1},{'uid':2}])
        uid=int(request.url.params['uid'])
        return httpx2.Response(200,json={'uid':uid,'id':'duplicate@example.test','subject':'Same envelope','body':'<p>Message</p>','attachments':[]})
    source=WebTop('https://mail.example.test',api_key='dedicated-key',username='alice@example.test',transport=mail_transport(handle))
    docs,_=source.page('INBOX')
    assert docs[0].remote_key!=docs[1].remote_key


def test_attachment_failures_are_explicit_and_parent_links_are_stable():
    def handle(request):
        if request.url.path=='/me/messages/list':return httpx2.Response(200,json=[{'uid':7}])
        return httpx2.Response(200,json={'uid':7,'id':'mail@example.test','body':'Hello','attachments':[
            {'id':'1','mimeType':'application/x-unknown','fileSize':100},
            {'id':'2','mimeType':'text/plain','fileSize':999999999}]})
    source=WebTop('https://mail.example.test',api_key='dedicated-key',username='alice@example.test',transport=mail_transport(handle))
    docs,coverage=source.page('INBOX')
    assert len(docs)==1
    assert coverage['attachment_observations'][0]['remote_key']==docs[0].remote_key
    assert [(x['attachment_id'],x['code']) for x in coverage['issues']]==[('1','unsupported_attachment'),('2','too_large')]


def test_supported_attachment_mime_parameters_use_normal_extraction_type():
    def handle(request):
        if request.url.path=='/me/messages/list':return httpx2.Response(200,json=[{'uid':7}])
        if request.url.path.endswith('/attachments/$value'):return httpx2.Response(200,content=b'Attachment body')
        return httpx2.Response(200,json={'uid':7,'id':'mail@example.test','body':'Hello','attachments':[
            {'id':'1','mimeType':'Text/Plain; charset=UTF-8','fileSize':15}]})
    source=WebTop('https://mail.example.test',api_key='dedicated-key',username='alice@example.test',transport=mail_transport(handle))
    docs,coverage=source.page('INBOX')
    assert docs[1].media_type=='text/plain' and docs[1].metadata['parent_import_key']==docs[0].remote_key
    assert coverage['issues']==[]


def test_webtop_refuses_an_authenticated_but_wrong_mailbox_identity():
    calls=[]
    def handle(request):
        calls.append(request.url.path)
        return httpx2.Response(200,json=[{'isMain':True,'email':'bob@example.test'}])
    source=WebTop('https://mail.example.test',api_key='dedicated-key',username='alice@example.test',transport=httpx2.MockTransport(handle))
    with pytest.raises(Unavailable) as error:source.folders()
    assert error.value.code=='identity_ambiguous' and calls==['/me/identities']
