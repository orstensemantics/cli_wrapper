"""
CLIWrapper represents calls to CLI tools as an object with native python function calls.
For example:
``` python
from json import loads  # or any other parser
from cli_wrapper import CLIWrapper
kubectl = CLIWrapper('kubectl')
kubectl._update_command("get", default_flags={"output": "json"}, parse=loads)
# this will run `kubectl get pods --namespace kube-system --output json`
result = kubectl.get("pods", namespace="kube-system")
print(result)

kubectl = CLIWrapper('kubectl', async_=True)
kubectl._update_command("get", default_flags={"output": "json"}, parse=loads)
result = await kubectl.get("pods", namespace="kube-system")  # same thing but async
print(result)
```

You can also override argument names and provide input validators:
``` python
from json import loads
from cli_wrapper import CLIWrapper
kubectl = CLIWrapper('kubectl')
kubectl._update_command("get_all", cli_command="get", default_flags={"output": "json", "A": None}, parse=loads)
result = kubectl.get_all("pods")  # this will run `kubectl get pods -A --output json`
print(result)

def validate_pod_name(name):
    return all(
        len(name) < 253,
        name[0].isalnum() and name[-1].isalnum(),
        all(c.isalnum() or c in ['-', '.'] for c in name[1:-1])
    )
kubectl._update_command("get", validators={1: validate_pod_name})
result = kubectl.get("pod", "my-pod!!")  # raises ValueError
```

Attributes:
    trusting: if false, only run defined commands, and validate any arguments that have validation. If true, run
        any command. This is useful for cli tools that have a lot of commands that you probably won't use, or for
        YOLO development.
    default_converter: if an argument for a command isn't defined, it will be passed to this. By default, it will
        just convert the name to kebab-case. This is useful for commands that have a lot of (rarely-used) arguments
        that you don't want to bother defining.
    arg_separator: what to put between a flag and its value. default is '=', so `command(arg=val)` would translate
        to `command --arg=val`. If you want to use spaces instead, set this to ' '
"""

import asyncio.subprocess
import logging
import os
import subprocess
from copy import copy
from itertools import chain

from attrs import define, field

from .parsers import Parser
from .transformers import transformers
from .validators import validators, Validator

logger = logging.getLogger(__name__)


@define
class Argument:
    """
    Argument represents a command line argument to be passed to the cli_wrapper
    """

    literal_name: str | None = None
    default: str = None
    validator: Validator | str | dict | list[str | dict] = field(converter=Validator, default=None)
    transformer: str = "snake2kebab"

    @classmethod
    def from_dict(cls, arg_dict):
        """
        Create an Argument from a dictionary
        :param arg_dict: the dictionary to be converted
        :return: Argument object
        """
        return Argument(
            literal_name=arg_dict.get("literal_name", None),
            default=arg_dict.get("default", None),
            validator=arg_dict.get("validator", None),
            transformer=arg_dict.get("transformer", None),
        )

    def to_dict(self):
        """
        Convert the Argument to a dictionary
        :return: the dictionary representation of the Argument
        """
        logger.debug(f"Converting argument {self.literal_name} to dict")
        return {
            "literal_name": self.literal_name,
            "default": self.default,
            "validator": self.validator.to_dict() if self.validator is not None else None,
        }

    def is_valid(self, value):
        """
        Validate the value of the argument
        :param value: the value to be validated
        :return: True if valid, False otherwise
        """
        logger.debug(f"Validating {self.literal_name} with value {value}")
        return validators.get(self.validator)(value) if self.validator is not None else True

    def transform(self, name, value, **kwargs):
        """
        Transform the value of the argument
        :param name: the name of the argument
        :param value: the value to be transformed
        :return: the transformed value
        """
        return (
            transformers.get(self.transformer)(name, value, **kwargs) if self.transformer is not None else (name, value)
        )


def cli_command_converter(value: str | list[str]):
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return value


def arg_converter(value: dict):
    """
    Convert the value of the argument to a string
    :param value: the value to be converted
    :return: the converted value
    """
    value = value.copy()
    for k, v in value.items():
        if isinstance(v, str):
            v = {"validator": v}
        if isinstance(v, dict):
            if "literal_name" not in v:
                v["literal_name"] = k
            value[k] = Argument.from_dict(v)
        if isinstance(v, Argument):
            if v.literal_name is None:
                v.literal_name = k
    return value


@define
class Command:  # pylint: disable=too-many-instance-attributes
    """
    Command represents a command to be run with the cli_wrapper
    """

    cli_command: list[str] | str = field(converter=cli_command_converter)
    default_flags: dict = {}
    args: dict[str | int, any] = field(factory=dict, converter=arg_converter)
    parse: Parser = field(converter=Parser, default=None)
    default_transformer: str = "snake2kebab"
    short_prefix: str = field(repr=False, default="-")
    long_prefix: str = field(repr=False, default="--")
    arg_separator: str = field(repr=False, default="=")

    @classmethod
    def from_dict(cls, command_dict, **kwargs):
        """
        Create a Command from a dictionary
        :param command_dict: the dictionary to be converted
        :return: Command object
        """
        command_dict = command_dict.copy()
        if "args" in command_dict:
            for k, v in command_dict["args"].items():
                if isinstance(v, dict):
                    if "literal_name" not in v:
                        v["literal_name"] = k
                if isinstance(v, Argument):
                    if v.literal_name is None:
                        v.literal_name = k
        if "cli_command" not in command_dict:
            command_dict["cli_command"] = kwargs.pop("cli_command", None)
        return Command(
            **command_dict,
            **kwargs,
        )

    def to_dict(self):
        """
        Convert the Command to a dictionary.
        Excludes prefixes/separators, because they are set in the CLIWrapper
        :return: the dictionary representation of the Command
        """
        logger.debug(f"Converting command {self.cli_command} to dict")
        return {
            "cli_command": self.cli_command,
            "default_flags": self.default_flags,
            "args": {k: v.to_dict() for k, v in self.args.items()},
            "parse": self.parse.to_dict() if self.parse is not None else None,
        }

    def validate_args(self, *args, **kwargs):
        # TODO: validate everything and raise comprehensive exception instead of just the first one
        for name, arg in chain(enumerate(args), kwargs.items()):
            logger.debug(f"Validating arg {name} with value {arg}")
            if name in self.args:
                logger.debug("Argument found in args")
                v = self.args[name].is_valid(arg)
                if isinstance(name, int):
                    name += 1  # let's call positional arg 0, "Argument 1"
                if isinstance(v, str):
                    raise ValueError(
                        f"Value '{arg}' is invalid for command {' '.join(self.cli_command)} arg {name}: {v}"
                    )
                if not v:
                    raise ValueError(f"Value '{arg}' is invalid for command {' '.join(self.cli_command)} arg {name}")

    def build_args(self, *args, **kwargs):
        positional = copy(self.cli_command) if self.cli_command is not None else []
        params = []
        for arg, value in chain(
            enumerate(args), kwargs.items(), [(k, v) for k, v in self.default_flags.items() if k not in kwargs]
        ):
            logger.debug(f"arg: {arg}, value: {value}")
            if arg in self.args:
                literal_arg = self.args[arg].literal_name if self.args[arg].literal_name is not None else arg
                arg, value = self.args[arg].transform(literal_arg, value)
            else:
                arg, value = transformers.get(self.default_transformer)(arg, value)
            logger.debug(f"after: arg: {arg}, value: {value}")
            if isinstance(arg, str):
                prefix = self.long_prefix if len(arg) > 1 else self.short_prefix
                if value is not None and not isinstance(value, bool):
                    if self.arg_separator != " ":
                        params.append(f"{prefix}{arg}{self.arg_separator}{value}")
                    else:
                        params.extend([f"{prefix}{arg}", value])
                else:
                    params.append(f"{prefix}{arg}")
            else:
                positional.append(value)
        result = positional + params
        logger.debug(result)
        return result


@define
class CLIWrapper:  # pylint: disable=too-many-instance-attributes
    path: str
    env: dict[str, str] = None
    commands: dict[str, Command] = {}

    trusting: bool = True
    raise_exc: bool = False
    async_: bool = False
    default_transformer: str = "snake2kebab"
    short_prefix: str = "-"
    long_prefix: str = "--"
    arg_separator: str = "="

    def _get_command(self, command: str):
        """
        get the command from the cli_wrapper
        :param command: the command to be run
        :return:
        """
        if command not in self.commands:
            if not self.trusting:
                raise ValueError(f"Command {command} not found in {self.path}")
            c = Command(
                cli_command=command,
                default_transformer=self.default_transformer,
                short_prefix=self.short_prefix,
                long_prefix=self.long_prefix,
                arg_separator=self.arg_separator,
            )
            return c
        return self.commands[command]

    def update_command_(  # pylint: disable=too-many-arguments
        self,
        command: str,
        *,
        cli_command: str | list[str] = None,
        args: dict[str | int, any] = None,
        default_flags: dict = None,
        parse=None,
    ):
        """
        update the command to be run with the cli_wrapper
        :param command: the command name for the wrapper
        :param cli_command: the command to be run, if different from the command name
        :param default_flags: default flags to be used with the command
        :param parse: function to parse the output of the command
        :return:
        """
        self.commands[command] = Command(
            cli_command=command if cli_command is None else cli_command,
            args=args if args is not None else {},
            default_flags=default_flags if default_flags is not None else {},
            parse=parse,
            default_transformer=self.default_transformer,
            short_prefix=self.short_prefix,
            long_prefix=self.long_prefix,
            arg_separator=self.arg_separator,
        )

    def _run(self, command: str, *args, **kwargs):
        """
        run the command with the cli_wrapper
        :param command: the subcommand for the cli tool
        :param args: arguments to be passed to the command
        :param kwargs: flags to be passed to the command
        :return:
        """
        command_obj = self._get_command(command)
        command_obj.validate_args(*args, **kwargs)
        command_args = [self.path] + command_obj.build_args(*args, **kwargs)
        env = os.environ.copy().update(self.env if self.env is not None else {})
        logger.debug(f"Running command: {' '.join(command_args)}")
        # run the command
        result = subprocess.run(command_args, capture_output=True, text=True, env=env, check=self.raise_exc)
        if result.returncode != 0:
            raise RuntimeError(f"Command {command} failed with error: {result.stderr}")
        return command_obj.parse(result.stdout)

    async def _run_async(self, command: str, *args, **kwargs):
        command_obj = self._get_command(command)
        command_obj.validate_args(*args, **kwargs)
        command_args = [self.path] + list(command_obj.build_args(*args, **kwargs))
        env = os.environ.copy().update(self.env if self.env is not None else {})
        logger.debug(f"Running command: {', '.join(command_args)}")
        proc = await asyncio.subprocess.create_subprocess_exec(  # pylint: disable=no-member
            *command_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"Command {command} failed with error: {stderr.decode()}")
        return command_obj.parse(stdout.decode())

    def __getattr__(self, item, *args, **kwargs):
        """
        get the command from the cli_wrapper
        :param item: the command to be run
        :return:
        """
        if self.async_:
            return lambda *args, **kwargs: self._run_async(item, *args, **kwargs)
        return lambda *args, **kwargs: self._run(item, *args, **kwargs)

    def __call__(self, *args, **kwargs):
        return (self.__getattr__(None))(*args, **kwargs)

    @classmethod
    def from_dict(cls, cliwrapper_dict):
        """
        Create a CLIWrapper from a dictionary
        :param cliwrapper_dict: the dictionary to be converted
        :return: CLIWrapper object
        """
        cliwrapper_dict = cliwrapper_dict.copy()
        commands = {}
        command_config = {
            "arg_separator": cliwrapper_dict.get("arg_separator", "="),
            "default_transformer": cliwrapper_dict.get("default_transformer", "snake2kebab"),
            "short_prefix": cliwrapper_dict.get("short_prefix", "-"),
            "long_prefix": cliwrapper_dict.get("long_prefix", "--"),
        }
        for command, config in cliwrapper_dict.pop("commands", {}).items():
            if isinstance(config, str):
                config = {"cli_command": config}
            else:
                if "cli_command" not in config:
                    config["cli_command"] = command
                config = command_config | config
            commands[command] = Command.from_dict(config)

        return CLIWrapper(
            commands=commands,
            **cliwrapper_dict,
        )

    def to_dict(self):
        """
        Convert the CLIWrapper to a dictionary
        :return:
        """
        return {
            "path": self.path,
            "env": self.env,
            "commands": {k: v.to_dict() for k, v in self.commands.items()},
            "trusting": self.trusting,
            "async_": self.async_,
            "default_transformer": self.default_transformer,
            "short_prefix": self.short_prefix,
            "long_prefix": self.long_prefix,
            "arg_separator": self.arg_separator,
        }
