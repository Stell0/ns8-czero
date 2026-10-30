# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Seed old layouts with installed predecessor persistence, never runtime shims."""
import importlib
import importlib.util
from pathlib import Path
import subprocess
import sys

from czero_core.identity import Role
from czero_core.spaces import SpaceService


def services(python):
    result=subprocess.run([str(python),'-I','-c','import czero_core;print(czero_core.__file__)'],capture_output=True,text=True,check=True)
    directory=Path(result.stdout.strip()).parent
    prefix='c0_previous_content_0352'
    if prefix not in sys.modules:
        spec=importlib.util.spec_from_file_location(prefix,directory/'__init__.py',submodule_search_locations=[str(directory)])
        module=importlib.util.module_from_spec(spec);sys.modules[prefix]=module;spec.loader.exec_module(module)
    old_knowledge=importlib.import_module(prefix+'.knowledge')
    old_sources=importlib.import_module(prefix+'.sources')
    old_jobs=importlib.import_module(prefix+'.jobs')
    class CurrentAuthorization:
        def _authorize(self,connection,actor,role=Role.READER):
            return SpaceService(self.database,self.access).authorize(connection,actor,Role(role.value),space_id=self._space_id)
    class PreviousKnowledge(CurrentAuthorization,old_knowledge.KnowledgeService):pass
    class PreviousSources(CurrentAuthorization,old_sources.SourceService):pass
    return PreviousKnowledge,PreviousSources,old_jobs.default_registry,old_sources.register_source_handlers
