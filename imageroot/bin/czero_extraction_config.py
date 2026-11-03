#!/usr/bin/env python3
# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Non-secret bounded native extraction configuration."""
import os

DEFAULTS={'enabled':False,'workers':2,'document_workers':2,'space_workers':2,
    'max_queued_units':2000,'max_staging_bytes':33554432,'ocr_enabled':False,'ocr_language':'eng'}
VARIABLES={'enabled':'CZERO_EXTRACTION_UNITS',**{key:'CZERO_EXTRACTION_'+key.upper() for key in DEFAULTS if key!='enabled'}}


def validate(value):
    if type(value) is not dict or set(value)!=set(DEFAULTS): raise ValueError('invalid_extraction_config')
    if type(value['ocr_enabled']) is not bool or value['ocr_language'] not in ('eng','ita','eng+ita'): raise ValueError('invalid_extraction_config')
    if type(value['enabled']) is not bool: raise ValueError('invalid_extraction_config')
    for key in ('workers','document_workers','space_workers'):
        if type(value[key]) is not int or not 1<=value[key]<=4: raise ValueError('invalid_extraction_config')
    for key,minimum,maximum in (('max_queued_units',200,4000),('max_staging_bytes',2097152,67108864)):
        if type(value[key]) is not int or not minimum<=value[key]<=maximum: raise ValueError('invalid_extraction_config')
    return dict(value)


def read(environment=None):
    environment=os.environ if environment is None else environment
    result={}
    for key,default in DEFAULTS.items():
        value=environment.get(VARIABLES[key],str(int(default)) if type(default) is bool else str(default))
        if type(default) is bool:
            if value not in ('0','1'): raise ValueError('invalid_extraction_config')
            result[key]=value=='1'
        elif key=='ocr_language': result[key]=value
        else:
            if not isinstance(value,str) or not value.isdecimal() or len(value)>9: raise ValueError('invalid_extraction_config')
            result[key]=int(value)
    return validate(result)


def merge(request,environment=None):
    if type(request) is not dict: raise ValueError('invalid_extraction_config')
    previous=read(environment)
    change=request.get('extraction',{})
    if type(change) is not dict or set(change)-set(DEFAULTS): raise ValueError('invalid_extraction_config')
    return validate({**previous,**change})


def encode(value):
    value=validate(value)
    result={VARIABLES[key]:str(int(item)) if type(item) is bool else str(item) for key,item in value.items()}
    result['CZERO_EXTRACTION_MEMORY']=str(value['workers'])+'g'
    result['CZERO_EXTRACTION_SWAP']=str(value['workers']*2)+'g'
    return result
