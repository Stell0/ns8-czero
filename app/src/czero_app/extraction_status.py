# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Browser progress and recovery over trusted Core operations."""
from uuid import UUID
from fastapi import Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from czero_core.extraction import ExtractionError
from czero_core.identity import PermissionDenied
from czero_core.sources import SourceConflict, SourceNotFound
from czero_app.auth import RequestAccess


class Revision(BaseModel):
    model_config=ConfigDict(extra='forbid')
    expected_revision:int=Field(strict=True,ge=1)


class Retry(Revision):
    idempotency_key:str=Field(min_length=1,max_length=128,pattern=r'^[A-Za-z0-9_.:-]+$')


def install(app,auth,sources,read_context,write_context):
    # Released consumers keep their original routes until adopting new Core.
    if not hasattr(sources,'reindex'): return
    from czero_core.extraction_queue import ExtractionQueue
    queue=ExtractionQueue(sources.database,sources.access,sources.originals)
    app.state.extraction_queue=queue
    def selected(space_id): return queue.in_space(space_id) if space_id is not None else queue
    def invoke(operation,*args,**kwargs):
        if auth is None: raise HTTPException(503,'authentication_not_configured')
        try: return operation(*args,**kwargs)
        except PermissionDenied: raise
        except SourceNotFound: raise HTTPException(404,'source_not_found') from None
        except SourceConflict: raise HTTPException(409,'source_conflict') from None
        except ExtractionError as error: raise HTTPException(422,error.code) from None
        except ValueError as error:
            code=str(error)
            if code=='content_superseded': raise HTTPException(410,code) from None
            allowed={'staging_expired','original_unavailable','managed_source_reindex'}
            raise HTTPException(422,code if code in allowed else 'invalid_extraction_request') from None

    @app.get('/api/v1/sources/{source_id}/extraction')
    def progress(source_id:UUID,space_id:UUID|None=None,context:RequestAccess=Depends(read_context)):
        return invoke(selected(space_id).progress,context.actor,source_id)

    @app.get('/api/v1/extraction-runs')
    def runs(space_id:UUID|None=None,limit:int=Query(50,ge=1,le=100),offset:int=Query(0,ge=0,le=10000),context:RequestAccess=Depends(read_context)):
        return {'runs':invoke(selected(space_id).runs,context.actor,limit=limit,offset=offset)}

    @app.get('/api/v1/extraction-runs/{run_id}/units')
    def units(run_id:UUID,space_id:UUID|None=None,limit:int=Query(50,ge=1,le=100),offset:int=Query(0,ge=0,le=10000),context:RequestAccess=Depends(read_context)):
        return invoke(selected(space_id).units,context.actor,run_id,limit=limit,offset=offset)

    @app.post('/api/v1/extraction-runs/{run_id}/retry')
    def retry(run_id:UUID,data:Retry,space_id:UUID|None=None,context:RequestAccess=Depends(write_context)):
        return invoke(selected(space_id).retry_failed,context.actor,run_id,**data.model_dump())

    @app.post('/api/v1/extraction-runs/{run_id}/cancel')
    def cancel(run_id:UUID,data:Revision,space_id:UUID|None=None,context:RequestAccess=Depends(write_context)):
        return invoke(selected(space_id).cancel,context.actor,run_id,**data.model_dump())

    @app.post('/api/v1/sources/{source_id}/reindex',status_code=202)
    def reindex(source_id:UUID,data:Retry,space_id:UUID|None=None,context:RequestAccess=Depends(write_context)):
        service=sources.in_space(space_id) if space_id is not None else sources
        return invoke(service.reindex,context.actor,source_id,**data.model_dump())
