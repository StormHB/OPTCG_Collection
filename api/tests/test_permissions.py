"""Predavanje 4: testovi uloga i vlasništva bez stvarne baze."""

from types import SimpleNamespace

import pytest

from app.core.errors import AppError
from app.core.permissions import require_role
from app.services.collection_service import ensure_collection_owner


def test_admin_moze_proci_admin_ovisnost():
    user = SimpleNamespace(id=1, role="admin")
    checker = require_role("admin")
    assert checker(current_user=user) is user


def test_obicni_korisnik_ne_moze_proci_admin_ovisnost():
    user = SimpleNamespace(id=2, role="user")
    checker = require_role("admin")
    with pytest.raises(AppError) as exc:
        checker(current_user=user)
    assert exc.value.status_code == 403
    assert exc.value.code == "forbidden"


def test_vlasnik_smije_pristupiti_svojoj_kolekciji():
    user = SimpleNamespace(id=7, role="user")
    assert ensure_collection_owner(user, 7) is None


def test_vlasnik_ne_smije_pristupiti_tudoj_kolekciji():
    user = SimpleNamespace(id=7, role="user")
    with pytest.raises(AppError) as exc:
        ensure_collection_owner(user, 8)
    assert exc.value.status_code == 403
    assert exc.value.code == "forbidden"


def test_admin_nema_automatski_pristup_tudoj_privatnoj_kolekciji():
    admin = SimpleNamespace(id=1, role="admin")
    with pytest.raises(AppError) as exc:
        ensure_collection_owner(admin, 8)
    assert exc.value.status_code == 403
