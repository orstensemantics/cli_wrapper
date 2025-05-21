from json import loads
from pathlib import Path

from ..cli_wrapper import CLIWrapper


def get_wrapper(name, status=None):
    """
    Gets a wrapper defined in the beta/stable folders as json.
    :param name: the name of the wrapper to retrieve
    :param status: stable/beta/None. None will search stable and beta
    :return: the requested wrapper
    """
    if status is None:
        status = ["stable", "beta"]
    if isinstance(status, str):
        status = [status]
    wrapper_config = None
    for d in status:
        path = Path(__file__).parent / d / f"{name}.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                wrapper_config = loads(f.read())
    if wrapper_config is None:
        raise ValueError(f"Wrapper {name} not found")
    return CLIWrapper.from_dict(wrapper_config)
