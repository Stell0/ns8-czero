# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
import io,json,urllib.error
from types import SimpleNamespace
import pytest
from github_vault.github_client import GitHub,GitHubError
from c0_ingest.errors import C0Error
from c0_projects.adapters import collect
from c0_projects.model import source_config
from c0_projects.private_sources import load_authorization,require_snapshot_permission


class Response(io.BytesIO):
    def __init__(self,value):super().__init__(json.dumps(value).encode());self.headers={}


def test_explicit_private_client_is_repo_bound_redacted_and_default_stays_public(tmp_path,monkeypatch,capsys):
    repo='fixture-c0-lab/synthetic-project';credential='synthetic-gh-credential'
    monkeypatch.setattr('github_vault.github_client.token',lambda:credential)
    calls=[]
    def open(request,**_):
        calls.append(request)
        if request.full_url.endswith('/synthetic-project'):return Response({'id':17,'full_name':repo,'private':True})
        return Response([{'id':27,'title':'Synthetic private issue','body':'Fabricated private fixture only.'}])
    client=GitHub(tmp_path,{'max_requests':5,'max_retries':0,'max_wait_seconds':1},opener=open,
        preserve_bodies=True,authorized_private_repository=repo)
    definition=source_config({'id':'private-repo','adapter':'github','repository':repo,'include':['issues']})
    batch=collect(definition,root=tmp_path,github=client,private_authorization_ref='synthetic:user-consent')
    assert batch.status=='complete' and batch.items[0].provenance['source_visibility']=='private'
    assert all(request.get_header('Authorization')=='Bearer '+credential for request in calls)
    with pytest.raises(GitHubError):client.get('/repos/unselected/other')
    logged=capsys.readouterr().err;assert credential not in logged and repo not in logged
    public=GitHub(tmp_path,{'max_requests':5,'max_retries':0,'max_wait_seconds':1},opener=open,anonymous=True,preserve_bodies=True)
    with pytest.raises(GitHubError):public.get('/repos/'+repo)
    assert public.token is None
    monkeypatch.setattr('github_vault.github_client.token',lambda:None)
    with pytest.raises(GitHubError):GitHub(tmp_path,{},authorized_private_repository=repo)


def test_private_consent_and_frozen_publication_require_the_exact_destination(tmp_path):
    repo='fixture-c0-lab/synthetic-project';space='11111111-1111-4111-8111-111111111111'
    definition=source_config({'id':'repo','adapter':'github','repository':repo})
    config={'project_space_id':space,'sources':[definition]};path=tmp_path/'consent.json'
    value={'schema_version':1,'project_space_id':space,'repositories':[repo],'authorization_ref':'synthetic:user'}
    path.write_text(json.dumps(value));path.chmod(0o600)
    authorizations=load_authorization(path,config)
    item={'provenance':{'source_visibility':'private','repository':repo,'repository_id':'17'}}
    with pytest.raises(C0Error):require_snapshot_permission(definition,[item],{})
    require_snapshot_permission(definition,[item],authorizations,preflight=lambda:{'id':17,'full_name':repo})
    with pytest.raises(C0Error):require_snapshot_permission(definition,[item],authorizations,preflight=lambda:{'id':99,'full_name':repo})
    path.write_text(json.dumps({**value,'project_space_id':'22222222-2222-4222-8222-222222222222'}))
    with pytest.raises(C0Error):load_authorization(path,config)
    path.chmod(0o644)
    with pytest.raises(C0Error):load_authorization(path,config)


def test_initial_repository_rate_limit_retains_retry_state(tmp_path):
    from time import time
    class Limited:
        def get(self,*_):raise GitHubError('synthetic rate limit',status=429,retry_at=time()+3600)
    definition=source_config({'id':'repo','adapter':'github','repository':'fixture-c0-lab/synthetic-project'})
    batch=collect(definition,root=tmp_path,github=Limited())
    assert batch.status=='partial' and batch.retry_after and batch.errors==['github_repository_unavailable']


@pytest.mark.parametrize('metadata',[[],{'private':False},{'id':False,'private':False}])
def test_invalid_remote_repository_metadata_is_partial(tmp_path,metadata):
    class Malformed:
        def get(self,*_):return metadata,None
    definition=source_config({'id':'repo','adapter':'github','repository':'fixture-c0-lab/synthetic-project'})
    batch=collect(definition,root=tmp_path,github=Malformed())
    assert batch.status=='partial' and not batch.items and batch.errors==['github_repository_metadata_invalid']
