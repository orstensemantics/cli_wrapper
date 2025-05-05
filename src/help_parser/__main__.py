import argparse
import logging

from cli_wrapper.cli_wrapper import CLIWrapper

logger = logging.getLogger(__name__)

type_validators = {
    "string": "is_str",
    "int": "is_int",
    "float": "is_float",
    "bool": "is_bool",
    "stringArray": "is_list",
}


def kebab2snake(name):
    return name.replace("-", "_")


def parse_golang_help(output):
    mode = None
    commands = []
    flags = {}
    for line in output.splitlines():
        logger.debug(line)
        if "Usage:" in line:
            logger.debug("Parsing usage section")
            mode = "usage"
            continue
        if "Options:" in line:
            logger.debug("Parsing options section")
            mode = "options"
            continue
        if "Flags:" in line:
            logger.debug("Parsing flags section")
            mode = "flags"
            continue
        if line.endswith(":") and "Commands" in line:
            logger.debug('Parsing section "%s"', line[:-1])
            mode = "commands"
            continue
        if mode == "flags":
            if "--" in line:
                flag_index = line.index("--") + 2
                flag_tokens = line[flag_index:].split()
                flag_name = flag_tokens[0]
                if flag_tokens[1] in type_validators:
                    validator = type_validators[flag_tokens[1]]
                else:
                    validator = type_validators["bool"]
                flags[flag_name] = validator
            continue
        if mode == "commands":
            if line.startswith("  "):
                command_name = line.split()[0]
                commands.append(command_name)
            continue
        if mode == "options":
            if line.startswith("  ") and "--" in line:
                flag_index = line.index("--") + 2
                equal_sign = line[flag_index:].index("=")
                flag_name = line[flag_index : flag_index + equal_sign]
                default_value = line[flag_index + equal_sign + 1 : -1].strip()
                match default_value:
                    case "true" | "false":
                        validator = type_validators["bool"]
                    case "[]":
                        validator = type_validators["stringArray"]  # TODO prove this
                    case _:
                        validator = type_validators["string"]
                flags[flag_name] = validator
                logger.debug("Flag name: %s, validator: %s", flag_name, validator)
    return commands, flags


def parse_help(config, output):
    match config.style:
        case "golang":
            commands, flags = parse_golang_help(output)
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
    return all([k in args for k in parser.keys()])


def available_defaults(args: dict[str], defaults: list[str]) -> dict[str, str]:
    return {key: args[key] for key in defaults if key in args}


def first_available_parser(args, parsers):
    for parser, flags in parsers.items():
        if parser_available(args, flags):
            return parser, flags
    return None, {}


def main(args):
    config = parse_args(args)
    command = config.command
    help_flag = config.help_flag

    cmd = CLIWrapper(command, arg_separator=config.default_separator)

    output = cmd(**{help_flag: True})

    commands, global_flags = parse_help(config, output)
    for command in commands:
        cmd_name = kebab2snake(command)
        cmd._update_command(cmd_name, default_flags=config.default_flags_dict, parse=None)
        output = cmd(command, **{help_flag: True})
        logger.info(f"Subcommands of {command}:")
        subcommands, cmd_flags = parse_help(config, output)
        cmd_args = global_flags | cmd_flags
        parser, parserflags = first_available_parser(cmd_args, config.default_parsers)
        cmd._update_command(
            cmd_name,
            default_flags=available_defaults(cmd_args, config.default_flags_dict) | parserflags,
            parse=parser,
            args=cmd_args,
        )
        for subcommand in subcommands:
            subcommand_name = kebab2snake(f"{command}_{subcommand}")
            cmd._update_command(
                subcommand_name,
                cli_command=[command, subcommand],
                args=cmd_args,
                default_flags=available_defaults(cmd_args, config.default_flags_dict),
            )
            output = cmd(command, subcommand, **{help_flag: True})
            _, subcmd_flags = parse_help(config, output)
            subcmd_args = cmd_args | subcmd_flags
            parser, parserflags = first_available_parser(subcmd_args, config.default_parsers)
            cmd._update_command(
                subcommand_name,
                cli_command=[command, subcommand],
                args=subcmd_args,
                default_flags=available_defaults(subcmd_args, config.default_flags_dict) | parserflags,
                parse=parser,
            )

    print(cmd.to_dict())


if __name__ == "__main__":
    import sys
    import os

    match os.environ.get("LOGLEVEL", "info").lower():
        case "debug":
            logging.basicConfig(level=logging.DEBUG)
        case "info":
            logging.basicConfig(level=logging.INFO)
        case "warning":
            logging.basicConfig(level=logging.WARNING)
        case "error":
            logging.basicConfig(level=logging.ERROR)

    main(sys.argv[1:])
