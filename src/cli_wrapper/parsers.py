import logging

logger = logging.getLogger(__name__)


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


DEFAULT_PARSERS = {
    "extract": extract,
}

try:
    from json import loads

    DEFAULT_PARSERS["json"] = loads
except ImportError:  # pragma: no cover
    pass
try:
    # prefer ruamel.yaml over PyYAML
    from ruamel.yaml import YAML

    def yaml_loads(src: str) -> dict:  # pragma: no cover
        #  pylint: disable=missing-function-docstring
        yaml = YAML(typ="safe")
        return yaml.load(src)

    DEFAULT_PARSERS["yaml"] = yaml_loads
except ImportError:  # pragma: no cover
    pass

if "yaml" not in DEFAULT_PARSERS:
    try:  # pragma: no cover
        from yaml import safe_load as yaml_loads

        DEFAULT_PARSERS["yaml"] = yaml_loads
    except ImportError:  # pragma: no cover
        pass

try:
    # https://github.com/josh-paul/dotted_dict -> lets us use dotted notation to access dict keys while preserving
    # the original key names. Syntactic sugar that makes nested dictionaries more palatable.
    from dotted_dict import PreserveKeysDottedDict

    def dotted_dictify(src, *args, **kwargs):
        if isinstance(src, list):
            return [PreserveKeysDottedDict(x) for x in src]
        if isinstance(src, dict):
            return PreserveKeysDottedDict(src)
        return src

    DEFAULT_PARSERS["dotted_dict"] = dotted_dictify
except ImportError:  # pragma: no cover
    pass


def get_parser(parser_name: str, args=None, kwargs=None) -> callable:
    """
    Retrieves a parser function based on the specified parser name.

    :param parser_name: The name of the parser to retrieve.
    :return: The corresponding parser function.
    :raises KeyError: If the specified parser name is not found.
    """
    if args is None:
        args = []
    if kwargs is None:
        kwargs = {}
    if callable(parser_name):
        return lambda x: parser_name(x, *args, **kwargs)
    if parser_name not in DEFAULT_PARSERS:
        raise KeyError(f"Parser '{parser_name}' not found.")
    parser = DEFAULT_PARSERS[parser_name]
    return lambda x: parser(x, *args, **kwargs)


def params_from_kwargs(src: dict | str) -> tuple[str, list, dict]:
    if isinstance(src, str):
        return src, [], {}
    assert len(src) == 1
    key = list(src.keys())[0]
    value = src[key]
    if isinstance(value, list):
        return key, value, {}
    if isinstance(value, dict):
        return key, value.pop("args", []), value


class Parser:
    parsers: list[callable]

    def __init__(self, config):
        self.parsers = []
        self.config = config
        if isinstance(config, str):
            self.parsers = [get_parser(config)]
        if isinstance(config, list):
            self.parsers = []
            for x in config:
                if callable(x):
                    self.parsers.append(x)
                else:
                    name, args, kwargs = params_from_kwargs(x)
                    self.parsers.append(get_parser(name, args, kwargs))
        if isinstance(config, dict):
            name, args, kwargs = params_from_kwargs(config)
            self.parsers = [get_parser(name, args, kwargs)]

    def __call__(self, input):
        # For now, parser expects to be called with one input.
        result = input
        for parser in self.parsers:
            logger.debug(result)
            result = parser(result)
        return result

    def _to_dict(self):
        return self.config
