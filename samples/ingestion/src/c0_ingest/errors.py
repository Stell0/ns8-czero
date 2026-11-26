# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
class C0Error(RuntimeError):
    """A bounded public diagnostic, without request bodies or credentials."""

    def __init__(self, message, *, code=None):
        super().__init__(message)
        self.code = code
