import pytest

from linkhop.adapters.base import AdapterCapabilities, AdapterError, ServiceAdapter
from linkhop.models.domain import ContentType


class _Full:
    service_id = "dummy"
    capabilities = AdapterCapabilities(track=True, album=False, artist=False)

    async def resolve(self, parsed):
        return None

    async def search(self, meta, target_type):
        return []


def test_protocol_accepts_full_implementation():
    assert isinstance(_Full(), ServiceAdapter)


def test_protocol_rejects_missing_method():
    class NoSearch:
        service_id = "dummy"
        capabilities = AdapterCapabilities(track=True, album=False, artist=False)

        async def resolve(self, parsed):
            return None

    assert not isinstance(NoSearch(), ServiceAdapter)


def test_protocol_rejects_missing_attribute():
    class NoServiceId:
        capabilities = AdapterCapabilities(track=True, album=False, artist=False)

        async def resolve(self, parsed):
            return None

        async def search(self, meta, target_type):
            return []

    assert not isinstance(NoServiceId(), ServiceAdapter)


@pytest.mark.parametrize(
    ("caps", "type_", "expected"),
    [
        (AdapterCapabilities(True, False, False), ContentType.TRACK, True),
        (AdapterCapabilities(True, False, False), ContentType.ALBUM, False),
        (AdapterCapabilities(False, True, False), ContentType.ALBUM, True),
        (AdapterCapabilities(False, False, True), ContentType.ARTIST, True),
        (AdapterCapabilities(True, True, True), ContentType.ARTIST, True),
    ],
)
def test_capabilities_supports(caps, type_, expected):
    assert caps.supports(type_) is expected


def test_adapter_error_str_and_raise():
    err = AdapterError("spotify", "not found")
    assert str(err) == "spotify: not found"
    assert err.args == ("spotify", "not found")
    with pytest.raises(AdapterError) as exc_info:
        raise err
    assert exc_info.value.service == "spotify"
    assert exc_info.value.message == "not found"
