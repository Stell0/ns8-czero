# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Validated native instance settings; request options never carry secrets."""
import base64
from dataclasses import dataclass
import json
import os
from .providers import EmbeddingSettings,ScorerSettings,EmbeddingClient,SystemOneClient
from .retrieval import SearchLimits


def default_config():
    return {'format':1,'embedding':{'enabled':False,'endpoint':'','model':'','dimensions':1536,
            'send_dimensions':False,'api_key':'','timeout':3},
        'scorer':{'mode':'off','endpoint':'','model':'','api_key':'','timeout':3,'threshold':.7},
        'limits':{'max_limit':50,'candidates':64,'graph_depth':3,'scorer_candidates':16}}


@dataclass(frozen=True)
class RetrievalSettings:
    embedding: EmbeddingSettings | None
    scorer: ScorerSettings | None
    scorer_mode: str
    limits: SearchLimits
    issue: str | None = None

    @classmethod
    def parse(cls,value):
        if not isinstance(value,dict) or set(value)!={'format','embedding','scorer','limits'} or type(value['format']) is not int or value['format']!=1:
            raise ValueError('invalid_retrieval_configuration')
        embedding,scorer,limits=value['embedding'],value['scorer'],value['limits']
        if (not isinstance(embedding,dict) or set(embedding)!={'enabled','endpoint','model','dimensions','send_dimensions','api_key','timeout'}
                or type(embedding['enabled']) is not bool or not isinstance(scorer,dict)
                or set(scorer)!={'mode','endpoint','model','api_key','timeout','threshold'}
                or scorer['mode'] not in ('off','rerank','filter') or not isinstance(limits,dict)
                or set(limits)!={'max_limit','candidates','graph_depth','scorer_candidates'}):
            raise ValueError('invalid_retrieval_configuration')
        # Disabled descriptors may retain a complete configuration for reuse;
        # only explicitly active providers construct network clients.
        eargs={k:v for k,v in embedding.items() if k!='enabled'}
        sargs={k:v for k,v in scorer.items() if k!='mode'}
        if any(not isinstance(args[key],str) for args in (eargs,sargs) for key in ('endpoint','model')):
            raise ValueError('invalid_retrieval_configuration')
        checked_e=EmbeddingSettings(**eargs) if embedding['enabled'] or embedding['endpoint'] or embedding['model'] else None
        checked_s=ScorerSettings(**sargs) if scorer['mode']!='off' or scorer['endpoint'] or scorer['model'] else None
        if checked_e is None:
            EmbeddingSettings('https://disabled.invalid/embeddings','disabled',**{k:eargs[k] for k in ('dimensions','send_dimensions','api_key','timeout')})
        if checked_s is None:
            ScorerSettings('https://disabled.invalid/systemone','disabled',**{k:sargs[k] for k in ('api_key','timeout','threshold')})
        return cls(checked_e if embedding['enabled'] else None,checked_s if scorer['mode']!='off' else None,
                   scorer['mode'],SearchLimits(**limits))

    def clients(self,*,transport=None):
        return (EmbeddingClient(self.embedding,transport=transport) if self.embedding else None,
                SystemOneClient(self.scorer,transport=transport) if self.scorer else None)


def load_settings():
    raw=os.getenv('CZERO_RETRIEVAL_CONFIG_B64','')
    if not raw:return RetrievalSettings.parse(default_config())
    try:
        if len(raw)>32768:raise ValueError('too_large')
        value=json.loads(base64.b64decode(raw,validate=True).decode('utf-8'))
        return RetrievalSettings.parse(value)
    except (ValueError,TypeError,KeyError,UnicodeError,RecursionError):
        defaults=RetrievalSettings.parse(default_config())
        return RetrievalSettings(None,None,'off',defaults.limits,'retrieval_configuration_invalid')
