from cli_wrapper.pre_packaged.beta.kubectl import get_kubectl


def test_kubectl_wrapper():
    kubectl = get_kubectl()

    result = kubectl.config_get_contexts()
    assert result is not None
