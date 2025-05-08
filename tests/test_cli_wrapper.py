import logging
from json import loads
from pathlib import Path

import pytest

from cli_wrapper.cli_wrapper import CLIWrapper, Argument, Command
from cli_wrapper.validators import validators

logger = logging.getLogger(__name__)


class TestArgument:
    def test_argument(self):
        arg = Argument("test", default="default", validator=lambda x: x == "valid")

        assert arg.is_valid("valid") is True
        assert arg.is_valid("invalid") is False
        assert arg.is_valid(None) is False

        with pytest.raises(KeyError):
            Argument("test", validator="not callable")

    def test_argument_from_dict(self):
        arg = Argument.from_dict({"literal_name": "test", "default": "default", "validator": lambda x: x == "valid"})

        assert arg.literal_name == "test"
        assert arg.default == "default"
        assert arg.is_valid("valid") is True
        assert arg.is_valid("invalid") is False
        assert arg.is_valid(None) is False

        arg = Argument.from_dict({})
        assert arg.literal_name is None
        assert arg.default is None
        assert arg.is_valid("valid") is True

        with pytest.raises(KeyError):
            Argument.from_dict({"name": "test", "validator": "nonexistent_validator"})


class TestCommand:
    def test_command(self):
        def validator(name):
            return "You can only get pods because I'm a jerk" if name not in ["pod", "pods"] else True

        validators.register_group(
            "test_command_group",
            {
                "is_pods": validator,
                "is_kube_system": lambda x: x == "kube-system",
            },
        )

        command = Command(
            cli_command="get",
            default_flags={"namespace": "default"},
            default_transformer="snake2kebab",
            args={
                0: {"validator": "test_command_group.is_pods"},
                "namespace": {"validator": "is_kube_system"},
            },
        )

        command.validate_args("pod", "pod-1", namespace="kube-system")
        with pytest.raises(ValueError) as err:
            command.validate_args("pod", "pod-2", namespace="tube-system")
        assert str(err.value) == "Value 'tube-system' is invalid for command get arg namespace"
        with pytest.raises(ValueError) as err:
            command.validate_args("deployments", "pod-1", namespace="kube-system")
        assert (
            str(err.value)
            == "Value 'deployments' is invalid for command get arg 1: You can only get pods because I'm a jerk"
        )

        args = command.build_args("pod", "pod-1", namespace="kube-system")
        logger.error(args)
        assert args == ["get", "pod", "pod-1", "--namespace=kube-system"]

        command.arg_separator = " "
        args = command.build_args("pod", "pod-1", namespace="kube-system")
        logger.debug(args)
        assert args == ["get", "pod", "pod-1", "--namespace", "kube-system"]

        args = command.build_args("pod", "pod-1", arg_without_value=None)
        assert args == ["get", "pod", "pod-1", "--arg-without-value", "--namespace", "default"]

        command = Command(
            cli_command="create",
            default_flags={"namespace": "default"},
            args={
                0: {"transformer": lambda x, y: ("filename", "filename")},
            },
        )
        args = command.build_args({"some": "dict"})
        assert args == ["create", "--filename=filename", "--namespace=default"]

        validators._all.pop("test_command_group")

    def test_command_from_dict(self):
        command = Command.from_dict(
            {
                "cli_command": "get",
                "default_flags": {"namespace": "default"},
                "args": {1: {"validator": lambda x: x == "pod-1"}},
            }
        )

        assert command.cli_command == ["get"]
        assert command.default_flags == {"namespace": "default"}
        assert command.args[1].is_valid("pod-1") is True
        assert command.args[1].is_valid("pod-2") is False

        with pytest.raises(ValueError):
            command.validate_args("pod", "pod-2", namespace="kube-system")
        assert command.build_args("pod", "pod-1", namespace="kube-system") == [
            "get",
            "pod",
            "pod-1",
            "--namespace=kube-system",
        ]

        command = Command.from_dict({"cli_command": "get", "args": {}})


class TestCLIWrapper:
    def test_cliwrapper(self):
        # fake kubectl script for github actions
        fake_kubectl = Path(__file__).parent / "data/fake_kubectl"
        kubectl = CLIWrapper(fake_kubectl.as_posix(), trusting=False)

        with pytest.raises(ValueError):
            kubectl.get("pods", namespace="kube-system")

        kubectl.trusting = True

        # test direct call (as used by help parser)
        r = kubectl("get", "pods", namespace="kube-system")
        assert isinstance(r, str)

        kubectl.update_command_("get")
        r = kubectl.get("pods", namespace="kube-system")

        assert isinstance(r, str)
        kubectl.commands["get"].default_flags = {"output": "json"}
        kubectl.commands["get"].parse = ["json"]

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
        fake_kubectl = Path(__file__).parent / "data/fake_kubectl"
        kubectl = CLIWrapper(fake_kubectl.as_posix(), trusting=True, async_=True)
        kubectl.update_command_("get", default_flags={"output": "json"}, parse=loads)
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
        assert cliwrapper.commands["get"].cli_command == ["get"]
        assert cliwrapper.commands["get"].default_flags == {"output": "json"}
        assert cliwrapper.commands["get"].parse('"some json"') == "some json"

        with pytest.raises(ValueError):
            cliwrapper.commands["get"].validate_args("pods", "my_cool_pod!!")
        with pytest.raises(ValueError):
            cliwrapper.get("pods", "my_cool_pod!!")
