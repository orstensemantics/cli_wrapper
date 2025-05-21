from typing import Callable

from attrs import define


@define
class CallableRegistry:
    """
    Stores collections of callables. @public
    - callables are registered by name
    - they are retrieved by name with args and kwargs
    - calling the callable with positional arguments will call the callable
      with the args in the call, plus any args and kwargs passed to get()
    """

    _all: dict[str, dict[str, Callable]]
    callable_name: str = "Callable thing"
    """ a name of the things in the registry to use in error messages """

    def get(self, name: str | Callable, args=None, kwargs=None) -> Callable:
        """
        Retrieves a callable function based on the specified parser name.

        :param name: The name of the callable to retrieve.
        :return: The corresponding callable function.
        :raises KeyError: If the specified callable name is not found.
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
            callable_group = self._all[group]
            if name not in callable_group:
                raise KeyError(f"{self.callable_name} '{name}' not found.")
            callable_ = callable_group[name]
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
        Registers a new callable function with the specified name.

        :param name: The name to associate with the callable.
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

    def register_group(self, name: str, callables: dict = None):
        """
        Registers a new callable group with the specified name.

        :param name: The name to associate with the callable group.
        :param callables: A dictionary of callables to register in the group.
        """
        if name in self._all:
            raise KeyError(f"{self.callable_name} group '{name}' already registered.")
        if "." in name:
            raise KeyError(f"{self.callable_name} group name '{name}' is not valid.")
        callables = {} if callables is None else callables
        bad_callable_names = [x for x in callables.keys() if "." in x]
        if bad_callable_names:
            raise KeyError(
                f"{self.callable_name} group '{name}' contains invalid callable names: {', '.join(bad_callable_names)}"
            )
        self._all[name] = callables

    def _parse_name(self, name: str) -> tuple[str, str]:
        """
        Parses a name into a group and callable name.

        :param name: The name to parse.
        :return: A tuple containing the group and callable name.
        """
        if "." not in name:
            return None, name
        try:
            group, name = name.split(".")
        except ValueError as err:
            raise KeyError(f"{self.callable_name} name '{name}' is not valid.") from err
        return group, name
