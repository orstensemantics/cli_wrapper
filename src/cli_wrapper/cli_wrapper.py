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

import asyncio
import logging
import os
import subprocess
from copy import deepcopy
from itertools import chain
from typing import Callable

from attrs import define

from cli_wrapper.parsers import Parser
from cli_wrapper.util import snake2kebab

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


@define
class Argument:
    """
    Argument represents a command line argument to be passed to the cli_wrapper
    """

    literal_name: str | None = None
    default: str = None
    validator: Callable[[str], bool | str] = None
    transformer: Callable[[str, str], tuple[str, str]] = None

    def __attrs_post_init__(self):
        if self.validator is None:
            self.validator = lambda x: True
        if not callable(self.validator):
            raise ValueError("Validator is not callable")
        if self.transformer is None:
            self.transformer = lambda name, value: (name, value)
        # TODO: support parser-style transformers (e.g. turn kubectl.create(dict) -> kubectl.create(filename=tmpfile(dict))
        # if isinstance(self.transformer, str):
        #     self.transformer = Parser(self.transformer)

    @classmethod
    def _from_dict(cls, arg_dict):
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

    def _to_dict(self):
        """
        Convert the Argument to a dictionary
        :return: the dictionary representation of the Argument
        """
        return {
            "literal_name": self.literal_name,
            "default": self.default,
            "validator": self.validator,
        }

    def is_valid(self, value):
        """
        Validate the value of the argument
        :param value: the value to be validated
        :return: True if valid, False otherwise
        """
        return self.validator(value) if self.validator is not None else True

    def transform(self, name, value, **kwargs):
        """
        Transform the value of the argument
        :param name: the name of the argument
        :param value: the value to be transformed
        :return: the transformed value
        """
        return self.transformer(name, value, **kwargs)


@define
class Command(object):
    """
    Command represents a command to be run with the cli_wrapper
    """

    cli_command: str
    default_flags: dict = {}
    args: dict[str | int, Argument] = {}
    parse: Callable[[str], any] = None
    default_transformer: Callable[[str, str], tuple[str, str]] = snake2kebab
    arg_separator: str = "="

    def __attrs_post_init__(self):
        if not callable(self.parse):
            logger.debug("Parse is not callable")
            self.parse = Parser(self.parse)

    @classmethod
    def _from_dict(cls, command_dict):
        """
        Create a Command from a dictionary
        :param command_dict: the dictionary to be converted
        :return: Command object
        """
        parse = command_dict.get("parse", None)
        if parse is not None:
            parse = Parser(parse)
        return Command(
            cli_command=command_dict.get("cli_command", None),
            default_flags=command_dict.get("default_flags", {}),
            args={k: Argument._from_dict(v) for k, v in command_dict.get("args", {}).items()},
            parse=parse,
            default_transformer=snake2kebab,
            arg_separator="=",
        )

    def _to_dict(self):
        """
        Convert the Command to a dictionary
        :return: the dictionary representation of the Command
        """
        return {
            "cli_command": self.cli_command,
            "default_flags": self.default_flags,
            "args": {k: v._to_dict() for k, v in self.args.items()},
            "parse": self.parse,
            "default_transformer": self.default_transformer,
            "arg_separator": self.arg_separator,
        }

    def validate_args(self, *args, **kwargs):
        # TODO: validate everything and raise comprehensive exception instead of just the first one
        for name, arg in chain(enumerate(args), kwargs.items()):
            if name in self.args:
                v = self.args[name].is_valid(arg)
                if isinstance(name, int):
                    name += 1  # let's call positional arg 0, "Argument 1"
                if isinstance(v, str):
                    raise ValueError(f"Argument {name} is invalid for command {self.cli_command}: {v}")
                if not v:
                    raise ValueError(f"Argument {name} is invalid for command {self.cli_command}")

    def build_args(self, *args, **kwargs):
        positional = [self.cli_command]
        params = []
        for arg, value in chain(
                enumerate(args), kwargs.items(), [(k, v) for k, v in self.default_flags.items() if k not in kwargs]
        ):
            logger.debug(f"arg: {arg}, value: {value}")
            if arg in self.args:
                arg = self.args[arg].literal_name if self.args[arg].literal_name is not None else arg
                arg, value = self.args[arg].transform(arg, value)
            else:
                arg, value = self.default_transformer(arg, value)
            logger.debug(f"after: arg: {arg}, value: {value}")
            if isinstance(arg, str):
                prefix = "--" if len(arg) > 1 else "-"
                if value is not None:
                    if self.arg_separator != " ":
                        params.append(f"{prefix}{arg}{self.arg_separator}{value}")
                    else:
                        params.extend([f"{prefix}{arg}", value])
                else:
                    params.append(f"{prefix}{arg}")
            else:
                positional.append(value)
            logger.debug(positional + params)
        result = positional + params
        logger.debug(result)
        return result


@define
class CLIWrapper:
    path: str
    env: dict[str, str] = None
    commands: dict[str, Command] = {}

    trusting: bool = True
    async_: bool = False
    default_transformer: Callable[[str, str], tuple[str, str]] = snake2kebab
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
                arg_separator=self.arg_separator,
                default_transformer=self.default_transformer,
            )
            logger.error(c.parse.__dict__)
            return c
        return self.commands[command]

    def _update_command(
            self,
            command: str,
            cli_command: str = None,
            args: dict[str | int, Argument] = None,
            default_flags: dict = None,
            parse=None,
    ):
        """
        update the command to be run with the cli_wrapper
        :param command: the subcommand for the cli tool
        :param default_flags: default flags to be used with the command
        :param parse: function to parse the output of the command
        :return:
        """
        if default_flags is None:
            default_flags = {}
        self.commands[command] = Command(
            cli_command=command if cli_command is None else cli_command,
            args=args if args is not None else {},
            default_flags=default_flags if default_flags is not None else {},
            parse=parse,
            default_transformer=self.default_transformer,
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
        result = subprocess.run(command_args, capture_output=True, text=True, env=env)
        if result.returncode != 0:
            raise RuntimeError(f"Command {command} failed with error: {result.stderr}")
        if command_obj.parse is not None:
            return command_obj.parse(result.stdout)
        return result.stdout

    async def _run_async(self, command: str, *args, **kwargs):
        command_obj = self._get_command(command)
        command_obj.validate_args(*args, **kwargs)
        command_args = [self.path] + list(command_obj.build_args(*args, **kwargs))
        env = os.environ.copy().update(self.env if self.env is not None else {})
        logger.error(f"Running command: {', '.join(command_args)}")
        proc = await asyncio.subprocess.create_subprocess_exec(
            *command_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"Command {command} failed with error: {stderr.decode()}")
        if command_obj.parse is not None:
            return command_obj.parse(stdout.decode())
        return stdout.decode()

    def __getattr__(self, item):
        """
        get the command from the cli_wrapper
        :param item: the command to be run
        :return:
        """
        if item not in self.commands and not self.trusting:
            raise ValueError(f"Command {item} not found in {self.path}")
        if self.async_:
            return lambda *args, **kwargs: self._run_async(item, *args, **kwargs)
        return lambda *args, **kwargs: self._run(item, *args, **kwargs)

    @classmethod
    def from_dict(cls, cliwrapper_dict):
        """
        Create a CLIWrapper from a dictionary
        :param cliwrapper_dict: the dictionary to be converted
        :return: CLIWrapper object
        """
        commands = {}
        for command, config in cliwrapper_dict.get("commands", {}).items():
            if isinstance(config, str):
                config = {"cli_command": config}
            else:
                if "cli_command" not in config:
                    config["cli_command"] = command
            commands[command] = Command._from_dict(config)

        return CLIWrapper(
            path=cliwrapper_dict.get("path"),
            env=cliwrapper_dict.get("env", {}),
            commands=commands,
            trusting=cliwrapper_dict.get("trusting", True),
            async_=cliwrapper_dict.get("async_", False),
            default_transformer=snake2kebab,
            arg_separator=cliwrapper_dict.get("arg_separator", "="),
        )
