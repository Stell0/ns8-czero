# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded JSON/YAML/TOML data, without executable tags or alias expansion."""
from copy import deepcopy
import json,math,tomllib
import yaml
from c0_ingest.errors import C0Error


def pairs(values):
    result={}
    for key,value in values:
        if type(key) is not str or key in result:raise ValueError('duplicate_or_nonstring_key')
        result[key]=value
    return result


class DataLoader(yaml.SafeLoader):
    yaml_implicit_resolvers=deepcopy(yaml.SafeLoader.yaml_implicit_resolvers)
    for _key,_resolvers in yaml_implicit_resolvers.items():
        yaml_implicit_resolvers[_key]=[(tag,expression) for tag,expression in _resolvers if tag!='tag:yaml.org,2002:timestamp']
    def __init__(self,stream):
        super().__init__(stream);self.nodes=0;self.depth=0
    def compose_node(self,parent,index):
        if self.check_event(yaml.AliasEvent):raise ValueError('yaml_alias_not_allowed')
        self.nodes+=1;self.depth+=1
        if self.nodes>10000 or self.depth>20:raise ValueError('data_structure_limit')
        try:
            node=super().compose_node(parent,index)
            if node.tag not in {'tag:yaml.org,2002:'+kind for kind in ('map','seq','str','int','float','bool','null')}:
                raise ValueError('yaml_tag_not_allowed')
            return node
        finally:self.depth-=1
    def construct_mapping(self,node,deep=False):
        return pairs((self.construct_object(key,deep=deep),self.construct_object(value,deep=deep)) for key,value in node.value)


def load_data(body,format,*,maximum=65536,max_nodes=10000):
    try:
        if type(body) is not str or len(body.encode())>maximum:raise ValueError('data_size_limit')
        if format=='json':
            def reject(_):raise ValueError('nonfinite_number')
            result=json.loads(body,object_pairs_hook=pairs,parse_constant=reject)
        elif format in ('yaml','yml'):
            loader=DataLoader(body)
            try:result=loader.get_single_data()
            finally:loader.dispose()
        elif format=='toml':result=tomllib.loads(body)
        else:raise ValueError('unsupported_data_format')
        pending=[(result,0)];count=0
        while pending:
            value,depth=pending.pop();count+=1
            if depth>20 or count>max_nodes:raise ValueError('data_structure_limit')
            if type(value) is dict:
                if any(type(key) is not str for key in value):raise ValueError('nonstring_key')
                pending.extend((item,depth+1) for item in value.values())
            elif type(value) is list:pending.extend((item,depth+1) for item in value)
            elif value is not None and type(value) not in (str,int,float,bool):raise ValueError('unsupported_data_type')
            elif type(value) is float and not math.isfinite(value):raise ValueError('nonfinite_number')
        return result
    except (ValueError,TypeError,RecursionError,yaml.YAMLError):raise C0Error('invalid_bounded_data') from None
