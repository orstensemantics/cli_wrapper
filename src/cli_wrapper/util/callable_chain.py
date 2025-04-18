from abc import ABC, abstractmethod


class CallableChain(ABC):
    chain: list[callable]
    config: list

    def __init__(self, config, source):
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
        Calls the chain of functions with the given value.
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
