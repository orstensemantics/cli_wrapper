"""
Utility functions for the CLI wrapper.
"""


def snake2kebab(arg: str, value: any) -> tuple[str, any]:
    """
    snake.gravity == 0
    """
    if isinstance(arg, str):
        return arg.replace("_", "-"), value
    # don't do anything if the arg is positional
    return arg, value
