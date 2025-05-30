import logging
from pathlib import Path
from uuid import uuid4

from .util.callable_chain import CallableChain
from .util.callable_registry import CallableRegistry

_logger = logging.getLogger(__name__)

core_validators = {
    "is_dict": lambda x: isinstance(x, dict),
    "is_list": lambda x: isinstance(x, list),
    "is_str": lambda x: isinstance(x, str),
    "is_str_or_list": lambda x: isinstance(x, (list, str)),
    "is_int": lambda x: isinstance(x, int),
    "is_bool": lambda x: isinstance(x, bool),
    "is_float": lambda x: isinstance(x, float),
    "is_alnum": lambda x: x.isalnum(),
    "is_alpha": lambda x: x.isalpha(),
    "is_digit": lambda x: x.isdigit(),
    "is_path": lambda x: isinstance(x, Path),
    "starts_alpha": lambda x: len(x) and x[0].isalpha(),
    "startswith": lambda x, prefix: x.startswith(prefix),
}

validators = CallableRegistry({"core": core_validators}, callable_name="Validator")


class Validator(CallableChain):
    """
    @public

    A class that provides a validation mechanism for input data.
    It uses a list of validators to check if the input data is valid.
    They are executed in sequence until one fails.
    """

    def __init__(self, config):
        if callable(config):
            id_ = str(uuid4())
            validators.register(id_, config)
            config = id_
        self.config = config
        super().__init__(config, validators)

    def __call__(self, value):
        result = True
        config = [self.config] if not isinstance(self.config, list) else self.config
        for x, c in zip(self.chain, config):
            validator_result = x(value)
            _logger.debug(f"Validator {c} result: {validator_result}")
            result = result and validator_result
            if isinstance(result, str) or not result:
                # don't bother doing other validations once one has failed
                _logger.debug("...failed")
                break
        return result

    def to_dict(self):
        """
        Converts the validator configuration to a dictionary.
        """
        _logger.debug(f"returning validator config: {self.config}")
        return self.config
