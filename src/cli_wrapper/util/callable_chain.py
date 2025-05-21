from abc import ABC, abstractmethod


class CallableChain(ABC):
    """
    A callable object representing a collection of callables.
    """

    chain: list[callable]
    config: list

    def __init__(self, config, source):
        """
        @public
        :param config: a callable, a string, a dictionary with one key and config, or a list of the previous
        :param source: a `CallableRegistry` to get callables from
        """
        self.chain = []
        self.config = config
        if callable(config):
            self.chain = [config]
        if isinstance(config, str):
            self.chain = [source.get(config)]
        if isinstance(config, list):
            self.chain = []
            for x in config:
                if callable(x):
                    self.chain.append(x)
                else:
                    name, args, kwargs = params_from_kwargs(x)
                    self.chain.append(source.get(name, args, kwargs))
        if isinstance(config, dict):
            name, args, kwargs = params_from_kwargs(config)
            self.chain = [source.get(name, args, kwargs)]

    def to_dict(self):
        return self.config

    @abstractmethod
    def __call__(self, value):
        """
        This function should be overridden by subclasses to determine how the
        callable chain is handled.
        """
        raise NotImplementedError()


def params_from_kwargs(src: dict | str) -> tuple[str, list, dict]:
    if isinstance(src, str):
        return src, [], {}
    assert len(src) == 1
    key = list(src.keys())[0]
    value = src[key]
    if isinstance(value, list):
        return key, value, {}
    if isinstance(value, dict):
        args = value.pop("args", [])
        if isinstance(args, str):
            args = [args]
        return key, args, value
    return key, [value], {}
