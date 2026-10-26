# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
from czero_core.project_workflows import near_copy


def test_question_identity_handles_unicode_punctuation_and_numeric_context():
    assert near_copy('WHAT changed: café capacity?', 'What changed café capacity!')
    assert not near_copy('What changed in release 1?', 'What changed in release 2?')
    assert not near_copy('What changed in manufacturing?', 'Who maintains repository documentation?')
    assert near_copy('capacity and constraints '*70, 'capacity and constraints '*70+'?')
