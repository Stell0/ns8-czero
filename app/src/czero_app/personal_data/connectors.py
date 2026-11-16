# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded existing-API readers. A failed read is never an authoritative inventory."""
import base64
from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import json
import re
import time
from urllib.parse import quote, urlsplit

import httpx2

from czero_core.extraction import MEDIA_TYPES, MAX_UPLOAD
from czero_core.personal_text import html_text


class Unavailable(ValueError):
    def __init__(self, code='source_unavailable'):
        if code not in {'source_unavailable','session_unavailable','capability_unverified','identity_ambiguous',
                        'inventory_incomplete','source_not_found','unsupported_attachment','too_large'}:
            code='source_unavailable'
        self.code=code
        super().__init__(code)


@dataclass(frozen=True)
class Document:
    remote_key: str
    kind: str
    title: str
    content: bytes = field(repr=False)
    media_type: str = 'text/plain'
    metadata: dict = field(default_factory=dict)


def _object_pairs(pairs):
    result={}
    for key,value in pairs:
        if key in result:
            raise Unavailable('capability_unverified')
        result[key]=value
    return result


class ReadClient:
    """Credentials stay on a single configured HTTPS origin; redirects are refused."""
    def __init__(self, base_url, headers, *, transport=None):
        url=urlsplit(base_url)
        if url.scheme!='https' or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ValueError('invalid_source_endpoint')
        self._base=base_url.rstrip('/')
        self._deadline=time.monotonic()+85
        self._remaining_requests=32
        # Every permitted response can reach the existing per-item upload limit.
        self._remaining_bytes=self._remaining_requests*MAX_UPLOAD
        self._client=httpx2.Client(headers=headers, timeout=10, follow_redirects=False, transport=transport,
                                    trust_env=False)

    def close(self):
        self._client.close()

    def read(self, path, *, params=None, body=None, binary=False):
        # POST is a documented read only for NethCTI status lookup.
        permitted = (path in {'/user/me','/history/calls','/history/statuses','/me/folders','/me/folders/children',
            '/me/messages/list','/me/messages','/me/identities','/me/messages/attachments/$value'}
            or re.fullmatch(r'/(transcripts|summary)/[A-Za-z0-9_.-]{1,128}',path))
        if not permitted or (body is not None and path!='/history/statuses'):
            raise ValueError('source_write_forbidden')
        if self._remaining_requests<=0 or time.monotonic()>=self._deadline:
            raise Unavailable('inventory_incomplete')
        self._remaining_requests-=1
        try:
            with self._client.stream('POST' if body is not None else 'GET', self._base+path,
                                     params=params, json=body) as response:
                if response.status_code in (401,403):
                    raise Unavailable('session_unavailable')
                if response.status_code==404:
                    raise Unavailable('source_not_found')
                if response.status_code!=200:
                    raise Unavailable()
                content=bytearray()
                for part in response.iter_bytes():
                    content.extend(part)
                    self._remaining_bytes-=len(part)
                    if self._remaining_bytes<0 or time.monotonic()>=self._deadline:
                        raise Unavailable('inventory_incomplete')
                    if len(content)>MAX_UPLOAD:
                        raise Unavailable('too_large')
                if binary:
                    return bytes(content)
                value=json.loads(content,object_pairs_hook=_object_pairs)
                if isinstance(value,dict) and (value.get('success') is False or
                        ('code' in value and value['code'] not in (200,'200'))):
                    raise Unavailable()
                return value
        except (httpx2.HTTPError, UnicodeError, json.JSONDecodeError):
            raise Unavailable() from None


def _data(value):
    return value['data'] if isinstance(value,dict) and 'data' in value else value


def _token_username(token):
    # Not a signature verifier. A successful upstream API read must also authenticate
    # this exact token; the claim only prevents routing an accepted token to another user.
    try:
        if not isinstance(token,str) or len(token)>16384:
            raise ValueError()
        parts=token.split('.')
        if len(parts)!=3:
            raise ValueError()
        value=json.loads(base64.urlsafe_b64decode(parts[1]+'='*(-len(parts[1])%4)),object_pairs_hook=_object_pairs)
        username=value['id']
        if not isinstance(username,str) or not username:
            raise ValueError()
        return username
    except (ValueError,KeyError,TypeError):
        raise Unavailable('identity_ambiguous') from None


class NethVoice:
    def __init__(self, base_url, *, token, username, phone_numbers=None, transport=None):
        if not token:
            raise Unavailable('session_unavailable')
        if _token_username(token)!=username or (phone_numbers is not None and (not phone_numbers or len(set(phone_numbers))!=len(phone_numbers))):
            raise Unavailable('identity_ambiguous')
        # Numbers must come from the current provider-backed profile, never from history.
        if any(not isinstance(n,str) or not re.fullmatch(r'\+?[0-9]{1,32}',n) for n in (phone_numbers or [])):
            raise Unavailable('identity_ambiguous')
        self.username=username
        self.numbers=set(phone_numbers or [])
        self.profile_verified=False
        self.client=ReadClient(base_url,{'Authorization':'Bearer '+token},transport=transport)

    def verify_profile(self):
        profile=_data(self.client.read('/user/me'))
        if not isinstance(profile,dict) or profile.get('username')!=self.username:
            raise Unavailable('identity_ambiguous')
        endpoints=profile.get('endpoints',{})
        extensions=endpoints.get('extension') if isinstance(endpoints,dict) else None
        if not isinstance(extensions,list):
            raise Unavailable('identity_ambiguous')
        numbers={v.get('id') for v in extensions if isinstance(v,dict)}
        if not numbers or any(not isinstance(n,str) or not re.fullmatch(r'\+?[0-9]{1,32}',n) for n in numbers):
            raise Unavailable('identity_ambiguous')
        self.numbers=numbers
        self.profile_verified=True

    def page(self, *, start, end, page=1, size=50):
        if not self.profile_verified:
            self.verify_profile()
        if not 1<=page<=100000 or not 1<=size<=100 or not re.fullmatch(r'\d{8}',start) or not re.fullmatch(r'\d{8}',end):
            raise ValueError('invalid_history_window')
        history=self.client.read('/history/calls',params={'callType':'user','username':self.username,
            'from':start,'to':end,'artifact':'transcription','pageNum':page,'pageSize':size})
        if not isinstance(history,dict) or not isinstance(history.get('rows'),list) or type(history.get('count')) is not int:
            raise Unavailable('capability_unverified')
        lookups=[]
        for row in history['rows']:
            if isinstance(row,dict) and isinstance(row.get('uniqueid'),str):
                lookups.append({'uniqueid':row['uniqueid'],'linkedid':row.get('linkedid','')})
        if not lookups:
            return [], {'complete':not history['rows'] and history['count']==0,'count':history['count'],'skipped':len(history['rows'])}
        statuses=_data(self.client.read('/history/statuses',body={'lookups':lookups,'switchboard':False}))
        if not isinstance(statuses,list):
            raise Unavailable('capability_unverified')
        documents=[]; skipped=0; seen=set()
        for item in statuses:
            if not isinstance(item,dict) or type(item.get('id')) is not int or item['id']<=0:
                skipped+=1; continue
            identifier=item['id']
            if identifier in seen:
                continue
            seen.add(identifier)
            src,dst=item.get('src_number'),item.get('dst_number')
            unique=item.get('uniqueid')
            if (not isinstance(src,str) or not isinstance(dst,str) or not src or not dst or src==dst
                    or not self.numbers.intersection({src,dst}) or not isinstance(unique,str)
                    or not re.fullmatch(r'[A-Za-z0-9_.-]{1,128}',unique) or item.get('state') not in ('done','completed')):
                skipped+=1; continue
            for endpoint,kind,field in (('transcripts','transcript','transcription'),('summary','summary','summary')):
                if not item.get('has_transcription' if kind=='transcript' else 'has_summary'):
                    continue
                detail=_data(self.client.read('/'+endpoint+'/'+unique,params={'id':identifier,'linkedid':item.get('linkedid','')}))
                if (not isinstance(detail,dict) or {detail.get('src'),detail.get('dst')}!={src,dst}
                        or not isinstance(detail.get(field),str) or not detail[field].strip()):
                    skipped+=1; continue
                timestamps={}
                for key in ('call_timestamp','created_at','updated_at'):
                    value=detail.get(key)
                    if isinstance(value,str) and len(value)<=64:
                        try:
                            if datetime.fromisoformat(value).tzinfo is not None:timestamps[key]=value
                        except ValueError:pass
                documents.append(Document(str(identifier),kind,('Transcript ' if kind=='transcript' else 'Summary ')+str(identifier),
                    detail[field].encode('utf-8'), metadata={'transcript_id':identifier,'uniqueid':unique,
                    'linkedid':item.get('linkedid'), 'derived':True,
                    'derivation':'existing_summary' if kind=='summary' else 'middleware_selected_transcription_variant_unverified',
                    'related_import_key':str(identifier),**timestamps}))
        return documents, {'complete':page*size>=history['count'],'count':history['count'],'skipped':skipped,
                           'deletion_authoritative':False}


def mail_uid(value):
    # Existing WebTop serializes IMAP's unsigned UID through a Java signed int.
    if type(value) is not int or not -2147483648<=value<=4294967295 or value==0:
        raise Unavailable('capability_unverified')
    return value & 0xffffffff


def mail_identity(message):
    message_id=message.get('id')
    identified=isinstance(message_id,str) and bool(message_id) and not message_id.startswith('uid:')
    fields={k:message.get(k) for k in ('id','subject','sender','recipients','date','sentDate','receivedDate')}
    if not identified:fields['body']=message.get('body')
    digest=hashlib.sha256(json.dumps(fields,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    return digest, 'message_id' if identified else 'content_hash'


class WebTop:
    EXCLUDED={'drafts','trash','spam','junk','shared','public'}
    def __init__(self, base_url, *, api_key, username, transport=None):
        if not api_key:
            raise Unavailable('session_unavailable')
        if not isinstance(username,str) or not username or any(c in username for c in '\r\n'):
            raise Unavailable('identity_ambiguous')
        self.username=username
        self.identity_verified=False
        self.client=ReadClient(base_url,{'Authorization':'Bearer '+api_key,'X-Auth-Username':username},transport=transport)

    def verify_identity(self):
        rows=_data(self.client.read('/me/identities'))
        if not isinstance(rows,list):raise Unavailable('identity_ambiguous')
        main=[r for r in rows if isinstance(r,dict) and r.get('isMain') is True]
        if len(main)!=1 or not isinstance(main[0].get('email'),str) or main[0]['email'].casefold()!=self.username.casefold():
            raise Unavailable('identity_ambiguous')
        self.identity_verified=True

    def folders(self, *, limit=500):
        if not self.identity_verified:self.verify_identity()
        pending=[None]; result=[]; seen=set()
        while pending:
            parent=pending.pop(0)
            rows=_data(self.client.read('/me/folders' if parent is None else '/me/folders/children',
                                        params=None if parent is None else {'folder_id':parent}))
            if not isinstance(rows,list):
                raise Unavailable('capability_unverified')
            for row in rows:
                if not isinstance(row,dict) or not isinstance(row.get('id'),str) or row['id'] in seen:
                    raise Unavailable('inventory_incomplete')
                seen.add(row['id'])
                if len(seen)>limit:
                    raise Unavailable('inventory_incomplete')
                # A type is required: unclassified/delegated folders fail closed.
                if row.get('type') not in {'inbox','sent','archive','other'}:
                    continue
                # Standard excluded ancestor/name guard complements source classification.
                if any(part.casefold() in self.EXCLUDED for part in re.split(r'[/\\.]',row['id'])):
                    continue
                result.append(row)
                if row.get('hasChildren') is True:
                    pending.append(row['id'])
        return result

    def page(self, folder, *, page=0, size=50):
        if not self.identity_verified:self.verify_identity()
        if type(page) is not int or not 0<=page<=100000 or type(size) is not int or not 1<=size<=100:
            raise ValueError('invalid_mail_page')
        rows=_data(self.client.read('/me/messages/list',params={'folder_id':folder,'page_no':page,'page_size':size}))
        if not isinstance(rows,list):
            raise Unavailable('capability_unverified')
        documents=[]; issues=[]; seen=set(); observations=[]
        for item in rows:
            uid=mail_uid(item.get('uid') if isinstance(item,dict) else None)
            if uid in seen:
                raise Unavailable('inventory_incomplete')
            seen.add(uid)
            message=_data(self.client.read('/me/messages',params={'folder_id':folder,'uid':uid,'set_seen':'false'}))
            if not isinstance(message,dict) or mail_uid(message.get('uid'))!=uid or not isinstance(message.get('body'),str):
                raise Unavailable('capability_unverified')
            # Always retrieve and hash actual content, even when folder/UID is unchanged.
            raw_hash=hashlib.sha256(json.dumps(message,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
            identity,identity_kind=mail_identity(message)
            slot=json.dumps([folder,uid],ensure_ascii=False,separators=(',',':'))
            key=json.dumps([folder,uid,identity],ensure_ascii=False,separators=(',',':'))
            subject=message.get('subject') or 'Mail message'
            if not isinstance(subject,str):raise Unavailable('capability_unverified')
            title=' '.join(re.sub(r'[\x00-\x1f\x7f]+',' ',subject).split())[:256].rstrip() or 'Mail message'
            metadata={'personal_import_slot':slot,'personal_identity_kind':identity_kind,'folder':folder,'uid':uid,'message_id':message.get('id'),'thread':message.get('threadId'),
                      'webtop_response_hash':raw_hash,'extraction':'webtop-html-to-text-v1','uidvalidity':'unavailable'}
            text='Subject: '+subject+'\n\n'+html_text(message['body'])
            if text.strip():
                documents.append(Document(key,'message',title[:256],text.encode(),metadata=metadata))
            message_issues=[]
            for attachment_index,attachment in enumerate(message.get('attachments') or []):
                attachment_id=attachment.get('id') if isinstance(attachment,dict) else None
                def issue(code):
                    value={'uid':uid,'attachment_id':str(attachment_id or 'unclassified:'+str(attachment_index))[:128],'code':code}
                    issues.append(value);message_issues.append(value)
                if not isinstance(attachment,dict) or not isinstance(attachment.get('id'),str):
                    issue('unsupported_attachment');continue
                media=attachment.get('mimeType');length=attachment.get('fileSize')
                media=media.partition(';')[0].strip().lower() if isinstance(media,str) else None
                if media not in MEDIA_TYPES or type(length) is not int or not 0<length<=MAX_UPLOAD:
                    issue('too_large' if type(length) is int and length>MAX_UPLOAD else 'unsupported_attachment');continue
                try:
                    data=self.client.read('/me/messages/attachments/$value',params={'folder_id':folder,'uid':uid,'index':attachment['id']},binary=True)
                except Unavailable as error:
                    issue(error.code);continue
                documents.append(Document(key+'/attachment/'+attachment['id'],'attachment',str(attachment.get('fileName') or title)[:256],
                    data,media,metadata={**metadata,'parent_import_key':key,'attachment_id':attachment['id']}))
            observations.append({'remote_key':key,'issues':message_issues})
        return documents, {'complete':len(rows)<size,'count':len(rows),'attachment_observations':observations,'issues':issues,'deletion_authoritative':False}
