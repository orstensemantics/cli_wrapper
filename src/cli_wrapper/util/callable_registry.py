from typing import Callable

from attrs import define


@define
class CallableRegistry:
    _all: dict[str, dict[str, Callable]]
    callable_name: str = "Callable thing"

    def get(self, name: str | Callable, args=None, kwargs=None) -> Callable:
        """
        Retrieves a parser function based on the specified parser name.

        :param name: The name of the parser to retrieve.
        :return: The corresponding parser function.
        :raises KeyError: If the specified parser name is not found.
        """
        if args is None:
            args = []
        if kwargs is None:
            kwargs = {}
        if callable(name):
            return lambda *fargs: name(*fargs, *args, **kwargs)
        callable_ = None
        group, name = self._parse_name(name)
        if group is not None:
            if group not in self._all:
                raise KeyError(f"{self.callable_name} group '{group}' not found.")
            parser_group = self._all[group]
            if name not in parser_group:
                raise KeyError(f"{self.callable_name} '{name}' not found.")
            callable_ = parser_group[name]
        else:
            for _, v in self._all.items():
                if name in v:
                    callable_ = v[name]
                    break
        if callable_ is None:
            raise KeyError(f"{self.callable_name} '{name}' not found.")
        return lambda *fargs: callable_(*fargs, *args, **kwargs)

    def register(self, name: str, callable_: callable, group="core"):
        """
        Registers a new parser function with the specified name.

        :param name: The name to associate with the parser.
        :param callable_: The callable function to register.
        """
        ngroup, name = self._parse_name(name)
        if ngroup is not None:
            if group != "core":
                # approximately, raise an exception if a group is specified in the name and the group arg
                raise KeyError(f"'{callable_}' already specifies a group.")
            group = ngroup
        if name in self._all[group]:
            raise KeyError(f"{self.callable_name} '{name}' already registered.")
        self._all[group][name] = callable_

    def register_group(self, name: str, parsers: dict = None):
        """
        Registers a new parser group with the specified name.

        :param name: The name to associate with the parser group.
        :param parsers: A dictionary of parsers to register in the group.
        """
        if name in self._all:
            raise KeyError(f"{self.callable_name} group '{name}' already registered.")
        if "." in name:
            raise KeyError(f"{self.callable_name} group name '{name}' is not valid.")
        parsers = {} if parsers is None else parsers
        bad_parser_names = [x for x in parsers.keys() if "." in x]
        if bad_parser_names:
            raise KeyError(
                f"{self.callable_name} group '{name}' contains invalid parser names: {', '.join(bad_parser_names)}"
            )
        self._all[name] = parsers

    def _parse_name(self, name: str) -> tuple[str, str]:
        """
        Parses a name into a group and parser name.

        :param name: The name to parse.
        :return: A tuple containing the group and parser name.
        """
        if "." not in name:
            return None, name
        try:
            group, name = name.split(".")
        except ValueError as err:
            raise KeyError(f"{self.callable_name} name '{name}' is not valid.") from err
        return group, name
