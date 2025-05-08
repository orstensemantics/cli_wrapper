import logging
import re

from help_parser.util import debug_line
from help_parser.validators import type_validators

logger = logging.getLogger(__name__)


def parse_golang_help(output, prefix):
    mode = None
    commands = []
    flags = {}
    option_re = re.compile(f"\\s+.*?{prefix}(?P<name>\\w[\\w-]+)(=(?P<default>[^:\\s]+))?(\\s(?P<type>[^:\\s]+))?:?.*?")

    for line in output.splitlines():
        debug_line(line)
        if line == "":
            continue
        if line.endswith(":") and line[0].isalpha():
            mode = state_change(line)
            continue
        match mode:
            case "flags":
                if prefix in line:
                    flag_index = line.index(prefix) + len(prefix)
                    flag_tokens = line[flag_index:].split()
                    flag_name = flag_tokens[0]
                    if flag_tokens[1] in type_validators:
                        validator = type_validators[flag_tokens[1]]
                    else:
                        validator = type_validators["bool"]
                    flags[flag_name] = validator
            case "commands":
                if line.startswith("  "):
                    # docker has some commands with * at the end in the help,
                    # which shouldn't be included
                    command_name: str = line.split()[0].replace("*", "")
                    commands.append(command_name)
            case "options":
                if line.startswith("  ") and prefix in line:
                    v = option_re.match(line)
                    if v is not None:
                        default_value = v.group("default")
                        flag_name = v.group("name")
                        flag_type = v.group("type")
                        if flag_type is not None:
                            logger.error(flag_type)
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


def state_change(line):
    mode = None
    if "usage" in line.lower():
        logger.debug("Parsing usage section")
        mode = "usage"
    if "options" in line.lower():
        logger.debug("Parsing options section")
        mode = "options"
    if "flags" in line.lower():
        logger.debug("Parsing flags section")
        mode = "flags"
    if "commands" in line.lower():
        logger.debug('Parsing section "%s"', line[:-1])
        mode = "commands"
    return mode
