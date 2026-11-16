# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Native settings/discovery. Only allowlisted public fields leave NS8 Redis."""
import json
import os
import stat
from pathlib import Path
from uuid import UUID, uuid4, uuid5, NAMESPACE_URL

DEFAULT={'enabled':False,'nethvoice':None,'webtop':None}


def validate(value):
    if type(value) is not dict or set(value)-set(DEFAULT) or type(value.get('enabled')) is not bool:
        raise ValueError('invalid_personal_data_config')
    result={**DEFAULT,**value}
    for key in ('nethvoice','webtop'):
        if result[key] is not None:
            if not isinstance(result[key],str):raise ValueError('invalid_personal_data_config')
            result[key]=str(UUID(result[key]))
    if result['enabled'] and not any(result[k] for k in ('nethvoice','webtop')):
        raise ValueError('personal_data_service_required')
    return result


def read(state=None):
    path=Path(state or os.environ['AGENT_STATE_DIR'])/'personal-data.json'
    return validate(json.loads(path.read_text())) if path.exists() else dict(DEFAULT)


def private_write(path,value):
    path=Path(path)
    temporary=path.with_name('.'+path.name+'.'+uuid4().hex+'.pending')
    descriptor=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:
        with os.fdopen(descriptor,'w') as out:
            os.fchmod(out.fileno(),0o600)
            json.dump(value,out,ensure_ascii=False)
            out.flush();os.fsync(out.fileno())
        os.replace(temporary,path)
    finally:temporary.unlink(missing_ok=True)


def provider_binding(parameters):
    # Bind the registered directory, not the node-local LDAP proxy port or credentials.
    if not isinstance(parameters,dict):raise ValueError('provider_unavailable')
    fields={k:parameters.get(k) for k in ('schema','location','base_dn','provider_ids')}
    if not all(fields.get(k) for k in fields):raise ValueError('provider_unavailable')
    fields['provider_ids']=sorted(fields['provider_ids'])
    return str(uuid5(NAMESPACE_URL,json.dumps(fields,sort_keys=True,separators=(',',':'))))


def registered_binding(rdb,domains,domain):
    parameters=domains.get(domain)
    if not isinstance(parameters,dict):raise ValueError('provider_unavailable')
    identities=[]
    for provider in parameters.get('providers',[]):
        if parameters['location']=='internal':
            identifier=rdb.hget('cluster/module_uuid',provider['id'])
            if not identifier:raise ValueError('provider_unavailable')
            identities.append(str(UUID(identifier)))
        else:
            identities.append(str(provider['host'])+':'+str(provider['port']))
    return provider_binding({**parameters,'provider_ids':identities})


def discover(rdb, ldapproxy, domain, *, domains=None):
    if domains is None:
        from cluster.userdomains import list_domains
        domains=list_domains(rdb)
    expected=registered_binding(rdb,domains,domain)
    result={'nethvoice':[],'webtop':[],'_mismatches':{'nethvoice':[],'webtop':[]}}
    counts={}
    for key in rdb.scan_iter(match='module/*/environment',count=100):
        module=key.split('/')[1]
        fields=('MODULE_UUID','USER_DOMAIN','NETHCTI_UI_HOST','WEBTOP_HOSTNAME','MAIL_MODULE','POSTFIX_ORIGIN')
        data=dict(zip(fields,rdb.hmget(key,fields)))
        kind='nethvoice' if data['NETHCTI_UI_HOST'] else ('webtop' if data['WEBTOP_HOSTNAME'] else None)
        if not kind:continue
        data['MODULE_UUID']=rdb.hget('cluster/module_uuid',module)
        if not data['MODULE_UUID']:continue
        counts[data['MODULE_UUID']]=counts.get(data['MODULE_UUID'],0)+1
        try:
            if kind=='nethvoice':
                actual=registered_binding(rdb,domains,data['USER_DOMAIN'])
                endpoint='https://'+data['NETHCTI_UI_HOST']+'/api'
            else:
                mail=data['MAIL_MODULE']
                if not mail:continue
                actual=registered_binding(rdb,domains,rdb.hget('module/'+mail+'/environment','POSTFIX_ORIGIN'))
                endpoint='https://'+data['WEBTOP_HOSTNAME']+'/webtop/api/com.sonicle.webtop.mail/v1'
            if actual!=expected:
                result['_mismatches'][kind].append(str(UUID(data['MODULE_UUID'])))
                continue
            result[kind].append({'id':str(UUID(data['MODULE_UUID'])),'label':module,'endpoint':endpoint})
        except (ValueError,TypeError,KeyError):
            continue
    # NS8 restores may temporarily duplicate a module UUID. Never choose a first match.
    for kind in ('nethvoice','webtop'):
        result[kind]=[row for row in result[kind] if counts.get(row['id'])==1]
        result['_mismatches'][kind]=[identifier for identifier in result['_mismatches'][kind] if counts.get(identifier)==1]
    return expected,result


def identity_binding(auth,previous):
    """A changed login issuer cannot adopt a previous private-space registry."""
    current=auth.get('CZERO_OIDC_ISSUER')
    prior=previous.get('issuer')
    return prior or current, bool(prior and current and prior!=current)


def private_read(path,maximum=1024*1024):
    descriptor=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(descriptor,'rb') as source:
        info=os.fstat(source.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or info.st_size>maximum:
            raise ValueError('invalid_personal_secret_file')
        value=source.read(maximum+1)
    if len(value)>maximum:raise ValueError('invalid_personal_secret_file')
    return json.loads(value)


def directory_user(client, schema, username):
    """Normalize the same immutable identity and active flags before/after source I/O."""
    attribute='objectGUID' if schema=='ad' else 'entryUUID'
    attrs=client.get_user_entry(username,lextra_attributes=[attribute,'pwdAccountLockedTime','userAccountControl','nsAccountLock'])['attributes']
    def first(key,default=None):
        value=attrs.get(key,default)
        return value[0] if isinstance(value,list) and value else value
    value=first(attribute)
    if isinstance(value,bytes):identifier=UUID(bytes_le=value) if attribute=='objectGUID' else UUID(value.decode('ascii'))
    else:identifier=UUID(str(value))
    locked=bool(first('pwdAccountLockedTime')) or str(first('nsAccountLock','false')).lower()=='true'
    disabled=bool(int(first('userAccountControl',0)) & 2)
    return {'directory_id':str(identifier),'username':username,'active':not locked and not disabled}


def current_directory_owner(client, schema, directory, message):
    if set(message)!={'binding_check','directory_id','username'} or message['binding_check'] is not True:
        return False
    expected={'directory_id':message['directory_id'],'username':message['username'],'active':True}
    if expected not in directory:return False
    return directory_user(client,schema,message['username'])==expected


def credentials_unchanged(path, expected):
    """An in-flight copy cannot regain authority after native clearing/rotation."""
    return (private_read(path) if Path(path).exists() else {})==expected
