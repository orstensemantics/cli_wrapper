import argparse
import json
import logging
from pathlib import Path

from cli_wrapper.cli_wrapper import CLIWrapper
from .golang_help import parse_golang_help

logger = logging.getLogger(__name__)


def kebab2snake(name):
    return name.replace("-", "_")


def parse_help(config, output):
    match config.style:
        case "golang":
            commands, flags = parse_golang_help(output, config.long_prefix)
        case _:
            raise ValueError(f"Unknown style: {config.style}")

    print(f"Commands: {commands}")
    print(f"Flags: {flags}")
    return commands, flags


def parse_args(argv):
    parser = argparse.ArgumentParser(description="Parse CLI command help.")
    parser.add_argument("command", type=str, help="The CLI command to parse.")
    parser.add_argument(
        "--help-flag",
        type=str,
        default="help",
        help="The flag to use for getting help (default: 'help').",
    )
    parser.add_argument(
        "--style",
        type=str,
        choices=["golang", "argparse"],
        default="golang",
        help="The style of cli help output (default: 'golang').",
    )
    parser.add_argument(
        "--default-flags",
        type=str,
        action="extend",
        nargs="+",
        help="Default flags to add to the command, key=value pairs.",
        default=[],
    )
    parser.add_argument(
        "--parser-default-pairs",
        type=str,
        default=None,
        action="extend",
        nargs="+",
        help="parser:key=value,... to configure default parsers.",
    )
    parser.add_argument(
        "--default-separator",
        type=str,
        default=" ",
        help="Default separator to use for command arguments.",
    )
    parser.add_argument(
        "--long-prefix",
        type=str,
        default="--",
        help="Default prefix for long flags.",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Output file to save the parsed command.",
    )

    config = parser.parse_args(argv)
    config.default_flags_dict = {}
    for f in config.default_flags:
        if "=" not in f:
            raise ValueError(f"Invalid default flag format: {f}. Expected key=value.")
        key, value = f.split("=")
        config.default_flags_dict[key] = value
    config.default_parsers = {}
    if config.parser_default_pairs:
        for pc in config.parser_default_pairs:
            parser, parserconfig = pc.split(":")
            parserconfig = parserconfig.split(",")
            flags = {}
            for pair in parserconfig:
                if "=" not in pair:
                    raise ValueError(f"Invalid parser default pair format: {pair}. Expected key=value.")
                key, value = pair.split("=")
                flags[key] = value
            config.default_parsers[parser] = flags
    return config


def parser_available(args: dict[str], parser: dict[str, str]) -> bool:
    return all(k in args for k in parser.keys())


def available_defaults(args: dict[str], defaults: list[str]) -> dict[str, str]:
    return {key: args[key] for key in defaults if key in args}


def first_available_parser(args, parsers):
    for parser, flags in parsers.items():
        if parser_available(args, flags):
            return parser, flags
    return None, {}


def main(args):  # pylint: disable=too-many-locals
    config = parse_args(args)
    command = config.command
    help_flag = config.help_flag

    cmd = CLIWrapper(command, arg_separator=config.default_separator, long_prefix=config.long_prefix)

    output = cmd(**{help_flag: True})

    commands, global_flags = parse_help(config, output)
    for command in commands:
        cmd_name = kebab2snake(command)
        cmd.update_command_(cmd_name, default_flags=config.default_flags_dict, parse=None)
        output = cmd(command, **{help_flag: True})
        logger.info(f"Subcommands of {command}:")
        subcommands, cmd_flags = parse_help(config, output)
        cmd_args = global_flags | cmd_flags
        parser, parserflags = first_available_parser(cmd_args, config.default_parsers)
        cmd.update_command_(
            cmd_name,
            default_flags=available_defaults(cmd_args, config.default_flags_dict) | parserflags,
            parse=parser,
            args=cmd_args,
        )
        for subcommand in subcommands:
            subcommand_name = kebab2snake(f"{command}_{subcommand}")
            cmd.update_command_(
                subcommand_name,
                cli_command=[command, subcommand],
                args=cmd_args,
                default_flags=available_defaults(cmd_args, config.default_flags_dict),
            )
            output = cmd(command, subcommand, **{help_flag: True})
            _, subcmd_flags = parse_help(config, output)
            subcmd_args = cmd_args | subcmd_flags
            parser, parserflags = first_available_parser(subcmd_args, config.default_parsers)
            cmd.update_command_(
                subcommand_name,
                cli_command=[command, subcommand],
                args=subcmd_args,
                default_flags=available_defaults(subcmd_args, config.default_flags_dict) | parserflags,
                parse=parser,
            )

    result = json.dumps(cmd.to_dict(), indent=2)
    if config.output:
        with config.output.open("w") as f:
            f.write(result)
    else:
        print(result)


if __name__ == "__main__":
    import sys
    import os

    match os.environ.get("LOGLEVEL", "info").lower():
        case "debug":
            print("Setting loglevel to debug")
            logging.basicConfig(level=logging.DEBUG)
        case "info":
            logging.basicConfig(level=logging.INFO)
        case "warning":
            logging.basicConfig(level=logging.WARNING)
        case "error":
            print("Setting loglevel to error")
            logging.basicConfig(level=logging.ERROR)

    logging.basicConfig(level=logging.ERROR)
    main(sys.argv[1:])
