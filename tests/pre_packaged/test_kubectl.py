from shutil import which

import pytest

from cli_wrapper.pre_packaged import get_wrapper


@pytest.mark.skipif(which("kubectl") is None, reason="Kubectl CLI not installed")
def test_kubectl_wrapper():
    kubectl = get_wrapper("kubectl")

    result = kubectl.config_get_contexts()
    assert result is not None
