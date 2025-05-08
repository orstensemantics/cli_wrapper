from shutil import which

import pytest

from cli_wrapper.pre_packaged import get_wrapper


@pytest.mark.skipif(which("cilium") is None, reason="Cilium CLI not installed")
def test_cilium():
    cilium = get_wrapper("cilium")
    assert cilium is not None

    version = cilium.version()
    assert version is not None
