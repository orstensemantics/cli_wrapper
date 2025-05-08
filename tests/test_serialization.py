from cli_wrapper import CLIWrapper
from cli_wrapper.cli_wrapper import Argument


class TestSerialization:
    def test_wrapper_to_dict(self):
        kubectl = CLIWrapper("kubectl", trusting=True)
        kubectl.update_command_(
            "get",
            default_flags={"output": "json"},
            parse="json",
            args={
                "namespace": {"validator": ["is_alnum", "starts_alpha"]},
            },
        )

        config = kubectl.to_dict()

        kubectl2 = CLIWrapper.from_dict(config)

        assert kubectl2.to_dict() == config

    def test_argument_to_dict(self):
        arg = Argument(
            literal_name="namespace",
            default="default",
            validator=["is_alnum", "starts_alpha"],
        )

        config = arg.to_dict()

        arg2 = Argument.from_dict(config)

        assert arg2.to_dict() == config
