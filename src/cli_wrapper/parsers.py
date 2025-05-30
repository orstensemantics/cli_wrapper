import logging

from .util.callable_chain import CallableChain
from .util.callable_registry import CallableRegistry

_logger = logging.getLogger(__name__)


def extract(src: dict, *args) -> dict:
    """
    Extracts a sub-dictionary from a source dictionary based on a given path.
    TODO: this

    :param src: The source dictionary to extract from.
    :param path: A list of keys representing the path to the sub-dictionary.
    :return: The extracted sub-dictionary.
    """
    for key in args:
        src = src[key]
    return src


core_parsers = {
    "extract": extract,
}

try:
    from json import loads

    core_parsers["json"] = loads
except ImportError:  # pragma: no cover
    pass
try:
    # prefer ruamel.yaml over PyYAML
    from ruamel.yaml import YAML

    def yaml_loads(src: str) -> dict:  # pragma: no cover
        #  pylint: disable=missing-function-docstring
        yaml = YAML(typ="safe")
        result = list(yaml.load_all(src))
        if len(result) == 1:
            return result[0]
        return result

    core_parsers["yaml"] = yaml_loads
except ImportError:  # pragma: no cover
    pass

if "yaml" not in core_parsers:
    try:  # pragma: no cover
        from yaml import safe_load as yaml_loads

        core_parsers["yaml"] = yaml_loads
    except ImportError:  # pragma: no cover
        pass

try:
    # https://github.com/josh-paul/dotted_dict -> lets us use dotted notation to access dict keys while preserving
    # the original key names. Syntactic sugar that makes nested dictionaries more palatable.
    from dotted_dict import PreserveKeysDottedDict

    def dotted_dictify(src, *args, **kwargs):
        if isinstance(src, list):
            return [dotted_dictify(x, *args, **kwargs) for x in src]
        if isinstance(src, dict):
            return PreserveKeysDottedDict(src)
        return src

    core_parsers["dotted_dict"] = dotted_dictify
except ImportError:  # pragma: no cover
    pass

parsers = CallableRegistry({"core": core_parsers}, callable_name="Parser")
"""
A `CallableRegistry` of parsers. These can be chained in sequence to perform 
operations on input.

Defaults:
core parsers:
 - json - parses the input as json, returns the result
 - extract - extracts the specified sub-dictionary from the source dictionary
 - yaml - parses the input as yaml, returns the result (requires ruamel.yaml or pyyaml)
 - dotted_dict - converts an input dictionary to a dotted_dict (requires dotted_dict)
"""


class Parser(CallableChain):
    """
    @public
    Parser class that allows for the chaining of multiple parsers. Callables in the configuration are run as a
    pipeline, with the output of one parser being passed as input to the next.
    """

    def __init__(self, config):
        super().__init__(config, parsers)

    def __call__(self, src):
        # For now, parser expects to be called with one input.
        result = src
        for parser in self.chain:
            _logger.debug(result)
            result = parser(result)
        return result
