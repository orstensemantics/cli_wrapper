import json
import logging
from json import loads

import pytest

from cli_wrapper.cli_wrapper import CLIWrapper, Argument, Command
from cli_wrapper.util import snake2kebab

logger = logging.getLogger(__name__)


class TestArgument:
    def test_argument(self):
        arg = Argument("test", default="default", validator=lambda x: x == "valid")

        assert arg.is_valid("valid") is True
        assert arg.is_valid("invalid") is False
        assert arg.is_valid(None) is False

        with pytest.raises(ValueError):
            Argument("test", validator="not callable")

    def test_argument_from_dict(self):
        arg = Argument._from_dict({"literal_name": "test", "default": "default", "validator": lambda x: x == "valid"})

        assert arg.literal_name == "test"
        assert arg.default == "default"
        assert arg.is_valid("valid") is True
        assert arg.is_valid("invalid") is False
        assert arg.is_valid(None) is False

        arg = Argument._from_dict({})
        assert arg.literal_name is None
        assert arg.default is None
        assert arg.is_valid("valid") is True

        with pytest.raises(ValueError):
            Argument._from_dict({"name": "test", "validator": "not callable"})


class TestCommand:
    def test_command(self):
        def parse_output(output):
            return output

        command = Command(
            cli_command="get",
            default_flags={"namespace": "default"},
            args={
                1: Argument(validator=lambda x: x == "pod-1"),
            },
        )

        command.validate_args("pod", "pod-1", namespace="kube-system")
        with pytest.raises(ValueError):
            command.validate_args("pod", "pod-2", namespace="kube-system")

        args = command.build_args("pod", "pod-1", namespace="kube-system")
        logger.error(args)
        assert args == ["get", "pod", "pod-1", "--namespace=kube-system"]

        command.arg_separator = " "
        args = command.build_args("pod", "pod-1", namespace="kube-system")
        assert args == ["get", "pod", "pod-1", "--namespace", "kube-system"]

        args = command.build_args("pod", "pod-1", arg_without_value=None)
        assert args == ["get", "pod", "pod-1", "--arg-without-value", "--namespace", "default"]

        command = Command(
            cli_command="create",
            default_flags={"namespace": "default"},
            args={
                0: Argument(transformer=lambda x, y: ("filename", "filename")),
            },
        )
        args = command.build_args({"some": "dict"})
        assert args == ["create", "--filename=filename", "--namespace=default"]

    def test_command_from_dict(self):
        command = Command._from_dict(
            {
                "cli_command": "get",
                "default_flags": {"namespace": "default"},
                "args": {1: {"validator": lambda x: x == "pod-1"}},
            }
        )

        assert command.cli_command == "get"
        assert command.default_flags == {"namespace": "default"}
        assert command.args[1].is_valid("pod-1") is True
        assert command.args[1].is_valid("pod-2") is False
        assert command.default_transformer == snake2kebab

        with pytest.raises(ValueError):
            command.validate_args("pod", "pod-2", namespace="kube-system")
        assert command.build_args("pod", "pod-1", namespace="kube-system") == [
            "get",
            "pod",
            "pod-1",
            "--namespace=kube-system",
        ]

        command = Command._from_dict({"cli_command": "get", "args": {}})


class TestCLIWrapper:
    def test_cliwrapper(self):
        logger.info("Testing CLIWrapper, trusting with get json/loads")
        kubectl = CLIWrapper("kubectl", trusting=True)
        kubectl._update_command("get", default_flags={"output": "json"}, parse=loads)

        r = kubectl.get("pods", "-A")
        assert r["kind"] == "List"
        assert r["items"] is not None

        logger.info("describe")
        r = kubectl.describe("pods", namespace="kube-system")
        # this should work with a trusting cli_wrapper
        assert r != ""

        logger.info("fake")
        with pytest.raises(RuntimeError):
            kubectl.fake("pods", namespace="kube-system")

        kubectl.trusting = False
        with pytest.raises(ValueError):
            kubectl.describe("pods", namespace="kube-system")
        logger.info("no parser")
        kubectl.commands["get"].parse = None
        r = kubectl.get("pods", namespace="kube-system")
        assert isinstance(r, str)

    @pytest.mark.asyncio
    async def test_subprocessor_async(self):
        kubectl = CLIWrapper("kubectl", trusting=True, async_=True)
        kubectl._update_command("get", default_flags={"output": "json"}, parse=loads)
        r = await kubectl.get("pods", namespace="kube-system")
        assert r["kind"] == "List"
        assert r["items"] is not None

        with pytest.raises(RuntimeError):
            await kubectl.fake("pods", namespace="kube-system")
        kubectl.commands["get"].parse = None
        r = await kubectl.get("pods", namespace="kube-system")
        assert isinstance(r, str)

    def test_cliwrapper_from_dict(self):
        def validate_resource_name(name):
            return all(
                [
                    len(name) < 253,
                    name[0].isalnum() and name[-1].isalnum(),
                    all(c.isalnum() or c in ["-", "."] for c in name[1:-1]),
                ]
            )

        cliwrapper = CLIWrapper.from_dict(
            {
                "path": "kubectl",
                "commands": {
                    "get": {
                        "default_flags": {"output": "json"},
                        "parse": "json",
                        "args": {
                            1: {"validator": validate_resource_name},
                        },
                    }
                },
            }
        )

        assert cliwrapper.path == "kubectl"
        assert cliwrapper.trusting is True
        assert cliwrapper.commands["get"].cli_command == "get"
        assert cliwrapper.commands["get"].default_flags == {"output": "json"}
        assert cliwrapper.commands["get"].parse('"some json"') == "some json"

        with pytest.raises(ValueError):
            cliwrapper.commands["get"].validate_args("pods", "my_cool_pod!!")
        with pytest.raises(ValueError):
            cliwrapper.get("pods", "my_cool_pod!!")
