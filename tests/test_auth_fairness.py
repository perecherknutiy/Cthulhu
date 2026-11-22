import time

import pytest

from app.fairness import FairRng, hash_seed
from app.services.users import parse_ref
from app.telegram_auth import InitDataError, validate_init_data
from tests.conftest import init_data

TOKEN = "123456:TEST-TOKEN"


def test_valid_init_data():
    d = validate_init_data(init_data(42, start_param="ref_7"), TOKEN, 3600)
    assert d.user.id == 42 and d.user.username == "user42" and d.start_param == "ref_7"


def test_tampered_init_data():
    raw = init_data(42).replace("user42", "user43")
    with pytest.raises(InitDataError, match="signature"):
        validate_init_data(raw, TOKEN, 3600)


def test_wrong_token():
    with pytest.raises(InitDataError):
        validate_init_data(init_data(42, token="999:OTHER"), TOKEN, 3600)


def test_expired_init_data():
    raw = init_data(42, auth_date=int(time.time()) - 7200)
    with pytest.raises(InitDataError, match="expired"):
        validate_init_data(raw, TOKEN, 3600)


def test_garbage():
    for raw in ["", "hash=", "a=b", "%%%"]:
        with pytest.raises(InitDataError):
            validate_init_data(raw, TOKEN, 3600)


def test_parse_ref():
    assert parse_ref("ref_123") == 123
    assert parse_ref("ref_abc") is None
    assert parse_ref(None) is None
    assert parse_ref("promo") is None


def test_rng_deterministic_and_in_range():
    a = FairRng("s" * 64, "client", 5).floats(100)
    b = FairRng("s" * 64, "client", 5).floats(100)
    c = FairRng("s" * 64, "client", 6).floats(100)
    assert a == b and a != c
    assert all(0 <= x < 1 for x in a)


def test_rng_known_vector():
    # фиксируем алгоритм: если тест упал — вы сломали совместимость проверки старых ставок
    f = FairRng("server", "client", 0).float()
    assert round(f, 10) == round(_reference_float("server", "client", 0), 10)


def _reference_float(server, client, nonce):
    import hashlib
    import hmac

    d = hmac.new(server.encode(), f"{client}:{nonce}:0".encode(), hashlib.sha256).digest()
    return d[0] / 256 + d[1] / 256**2 + d[2] / 256**3 + d[3] / 256**4


def test_shuffle_is_permutation():
    rng = FairRng("x", "y", 1)
    out = rng.shuffle(list(range(25)))
    assert sorted(out) == list(range(25))


def test_hash_seed():
    assert hash_seed("abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
