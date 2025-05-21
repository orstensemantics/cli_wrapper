from .util.callable_registry import CallableRegistry


def snake2kebab(arg: str, value: any) -> tuple[str, any]:
    """
    `snake.gravity = 0`

    converts a snake_case argument to a kebab-case one
    """
    if isinstance(arg, str):
        return arg.replace("_", "-"), value
    # don't do anything if the arg is positional
    return arg, value


core_transformers = {
    "snake2kebab": snake2kebab,
}
""" @private """

transformers = CallableRegistry({"core": core_transformers})
"""
A callable registry of transformers.

Defaults:
core group:
 - snake2kebab
"""
