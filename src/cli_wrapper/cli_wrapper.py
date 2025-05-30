import asyncio.subprocess
import logging
import os
import subprocess
from copy import copy
from itertools import chain
from typing import Callable

from attrs import define, field

from .parsers import Parser
from .transformers import transformers
from .validators import validators, Validator

_logger = logging.getLogger(__name__)


@define
class Argument:
    """
    Argument represents a command line argument to be passed to the cli_wrapper
    """

    literal_name: str | None = None
    """ @private """
    default: str = None
    """ @private """
    validator: Validator | str | dict | list[str | dict] = field(converter=Validator, default=None)
    """ @private """
    transformer: Callable | str | dict | list[str | dict] = "snake2kebab"
    """ @private """

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
        _logger.debug(f"Converting argument {self.literal_name} to dict")
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
        _logger.debug(f"Validating {self.literal_name} with value {value}")
        return validators.get(self.validator)(value) if self.validator is not None else True

    def transform(self, name, value, **kwargs):
        """
        Transform the name and value of the argument
        :param name: the name of the argument
        :param value: the value to be transformed
        :return: the transformed value
        """
        return (
            transformers.get(self.transformer)(name, value, **kwargs) if self.transformer is not None else (name, value)
        )


def _cli_command_converter(value: str | list[str]):
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return value


def _arg_converter(value: dict):
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

    cli_command: list[str] | str = field(converter=_cli_command_converter)
    """ @private """
    default_flags: dict = {}
    """ @private """
    args: dict[str | int, any] = field(factory=dict, converter=_arg_converter)
    """ @private """
    parse: Parser = field(converter=Parser, default=None)
    """ @private """
    default_transformer: str = "snake2kebab"
    """ @private """
    short_prefix: str = field(repr=False, default="-")
    """ @private """
    long_prefix: str = field(repr=False, default="--")
    """ @private """
    arg_separator: str = field(repr=False, default="=")
    """ @private """

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
        _logger.debug(f"Converting command {self.cli_command} to dict")
        return {
            "cli_command": self.cli_command,
            "default_flags": self.default_flags,
            "args": {k: v.to_dict() for k, v in self.args.items()},
            "parse": self.parse.to_dict() if self.parse is not None else None,
        }

    def validate_args(self, *args, **kwargs):
        # TODO: validate everything and raise comprehensive exception instead of just the first one
        for name, arg in chain(enumerate(args), kwargs.items()):
            _logger.debug(f"Validating arg {name} with value {arg}")
            if name in self.args:
                _logger.debug("Argument found in args")
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
            _logger.debug(f"arg: {arg}, value: {value}")
            if arg in self.args:
                literal_arg = self.args[arg].literal_name if self.args[arg].literal_name is not None else arg
                arg, value = self.args[arg].transform(literal_arg, value)
            else:
                arg, value = transformers.get(self.default_transformer)(arg, value)
            _logger.debug(f"after: arg: {arg}, value: {value}")
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
        _logger.debug(result)
        return result


@define
class CLIWrapper:  # pylint: disable=too-many-instance-attributes
    """
    :param path: The path to the CLI tool. This will be passed to subprocess directly, and does not require a full path
      unless the tool is not in the system path.
    :param env: A dict of environment variables to be set in the subprocess environment, in addition to and overriding
      those in os.environ.
    :param trusting: If True, the wrapper will accept any command and pass them to the cli with default configuration.
      Otherwise, it will only allow commands that have been defined with `update_command_`
    :param raise_exc: If True, the wrapper will raise an exception if a command returns a non-zero exit code.
    :param async_: If true, the wrapper will return coroutines that must be awaited.
    :param default_transformer: The transformer configuration to apply to all arguments. The default of snake2kebab will
      convert pythonic_snake_case_kwargs to kebab-case-arguments
    :param short_prefix: The string prefix for single-letter arguments
    :param long_prefix: The string prefix for arguments longer than 1 letter
    :param arg_separator: The character that separates argument values from names. Defaults to '=', so
      wrapper.command(arg=value) would become "wrapper command --arg=value"
    """

    path: str
    """ @private """
    env: dict[str, str] = None
    """ @private """
    _commands: dict[str, Command] = {}
    """ @private """

    trusting: bool = True
    """ @private """
    raise_exc: bool = False
    """ @private """
    async_: bool = False
    """ @private """
    default_transformer: str = "snake2kebab"
    """ @private """
    short_prefix: str = "-"
    """ @private """
    long_prefix: str = "--"
    """ @private """
    arg_separator: str = "="
    """ @private """

    def _get_command(self, command: str):
        """
        get the command from the cli_wrapper
        :param command: the command to be run
        :return:
        """
        if command not in self._commands:
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
        return self._commands[command]

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
        :param args: the arguments passed to the command
        :param default_flags: default flags to be used with the command
        :param parse: function to parse the output of the command
        :return:
        """
        self._commands[command] = Command(
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
        command_obj = self._get_command(command)
        command_obj.validate_args(*args, **kwargs)
        command_args = [self.path] + command_obj.build_args(*args, **kwargs)
        env = os.environ.copy().update(self.env if self.env is not None else {})
        _logger.debug(f"Running command: {' '.join(command_args)}")
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
        _logger.debug(f"Running command: {', '.join(command_args)}")
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
        """
        Invokes the wrapper with no extra arguments. e.g., for the kubectl wrapper, calls bare kubectl.
        `kubectl(help=True)` will be interpreted as "kubectl --help".
        :param args: positional arguments to be passed to the command
        :param kwargs: kwargs will be treated as `--options`. Boolean values will be bare flags, others will be
          passed as `--kwarg=value` (where `=` is the wrapper's arg_separator)
        :return:
        """
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
        :return: a dictionary that can be used to recreate the wrapper using `from_dict`
        """
        return {
            "path": self.path,
            "env": self.env,
            "commands": {k: v.to_dict() for k, v in self._commands.items()},
            "trusting": self.trusting,
            "async_": self.async_,
            "default_transformer": self.default_transformer,
            "short_prefix": self.short_prefix,
            "long_prefix": self.long_prefix,
            "arg_separator": self.arg_separator,
        }
