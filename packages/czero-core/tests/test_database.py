# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import OperationalError

from czero_core.database import Database


def test_database_url_errors_do_not_echo_secrets():
    for value in ('not a url:secret-value', 'sqlite:///secret-value'):
        with pytest.raises(ValueError) as error:
            Database(value)
        assert 'secret-value' not in str(error.value)


def test_failed_health_hides_driver_errors():
    @contextmanager
    def connect():
        raise OperationalError('connect', {}, Exception('password=secret-value'))
        yield
    database = Database.__new__(Database)
    database.engine = SimpleNamespace(connect=connect)
    assert database.health() == {'status':'unavailable','reason':'database_unavailable'}
