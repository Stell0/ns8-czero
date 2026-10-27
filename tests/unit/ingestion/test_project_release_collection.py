# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
import json
import pytest
from c0_ingest.errors import C0Error
from c0_projects.fetch import FetchError
from c0_projects.maintenance import collect_release,validate_release_plan


class Fetch:
    def __init__(self,values):self.values=iter(values);self.urls=[]
    def get(self,url):
        self.urls.append(url);value=next(self.values)
        if isinstance(value,Exception):raise value
        return json.dumps(value).encode(),url,'application/json'


def test_release_collector_resolves_actual_tag_and_never_downloads_assets():
    fetch=Fetch([{'full_name':'Stell0/ns8-czero','private':False},
        {'id':17,'tag_name':'core-v0.34.0','draft':False,'prerelease':False},
        {'object':{'type':'tag','sha':'a'*40}},{'object':{'type':'commit','sha':'b'*40}}])
    result=collect_release('Stell0/ns8-czero',fetch)
    assert result=={'repository':'Stell0/ns8-czero','complete':True,'fresh':True,
        'releases':[{'version':'core-v0.34.0','release_id':'17','source_commit':'b'*40}]}
    assert len(fetch.urls)==4 and all(url.startswith('https://api.github.com/repos/Stell0/ns8-czero') for url in fetch.urls)
    assert not any('/assets/' in url for url in fetch.urls)


def test_no_release_requires_a_successful_public_repository_observation():
    fetch=Fetch([{'full_name':'Kabutojira/WikiPlant','private':False},FetchError('source_http_404')])
    assert collect_release('Kabutojira/WikiPlant',fetch)['releases']==[]
    with pytest.raises(FetchError):collect_release('Kabutojira/WikiPlant',Fetch([FetchError('source_http_404')]))


def test_rate_limits_and_untrusted_or_unresolved_metadata_are_not_up_to_date():
    with pytest.raises(FetchError):collect_release('Stell0/ns8-czero',Fetch([
        {'full_name':'Stell0/ns8-czero','private':False},FetchError('source_http_429')]))
    with pytest.raises(C0Error):collect_release('https://internal.invalid',Fetch([]))
    with pytest.raises(C0Error):collect_release('Stell0/ns8-czero',Fetch([
        {'full_name':'Stell0/ns8-czero','private':False},
        {'id':17,'tag_name':'v0.34.0','draft':False,'prerelease':False},{'object':{'type':'commit','sha':None}}]))


def test_release_plan_rejects_invalid_lease_before_any_collection():
    with pytest.raises(C0Error):validate_release_plan({'lease':{'run_id':'','lease_owner':'worker','fencing_generation':True},
        'repository':'Kabutojira/WikiPlant','installed_version':'0.1.0'})
