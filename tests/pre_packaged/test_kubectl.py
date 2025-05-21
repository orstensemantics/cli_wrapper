from pathlib import Path
from shutil import which

import pytest

from cli_wrapper.pre_packaged import get_wrapper


@pytest.mark.skipif(which("kubectl") is None, reason="Kubectl CLI not installed")
def test_kubectl_wrapper():
    kubectl = get_wrapper("kubectl")

    result = kubectl.config_get_contexts()
    assert result is not None


@pytest.mark.skipif(which("kubectl") is not None, reason="skipping fake kubectl test because real kubectl exists")
def test_kubectl_wrapper_fake():
    kubectl = get_wrapper("kubectl")
    kubectl.path = (Path(__file__).parent.parent / "data" / "fake_kubectl").as_posix()

    result = kubectl.get_pods()
    assert result is not None
