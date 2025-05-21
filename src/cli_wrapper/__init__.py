"""
CLIWrapper represents calls to CLI tools as an object with native python function calls.

# Examples

```
from json import loads  # or any other parser
from cli_wrapper import CLIWrapper
kubectl = CLIWrapper('kubectl')
kubectl._update_command("get", default_flags={"output": "json"}, parse=loads)
# this will run `kubectl get pods --namespace kube-system --output json`
result = kubectl.get("pods", namespace="kube-system")
print(result)

kubectl = CLIWrapper('kubectl', async_=True)
kubectl._update_command("get", default_flags={"output": "json"}, parse=loads)
result = await kubectl.get("pods", namespace="kube-system")  # same thing but async
print(result)
```

You can also override argument names and provide input validators:
```
from json import loads
from cli_wrapper import CLIWrapper
kubectl = CLIWrapper('kubectl')
kubectl._update_command("get_all", cli_command="get", default_flags={"output": "json", "A": None}, parse=loads)
result = kubectl.get_all("pods")  # this will run `kubectl get pods -A --output json`
print(result)

def validate_pod_name(name):
    return all(
        len(name) < 253,
        name[0].isalnum() and name[-1].isalnum(),
        all(c.isalnum() or c in ['-', '.'] for c in name[1:-1])
    )
kubectl._update_command("get", validators={1: validate_pod_name})
result = kubectl.get("pod", "my-pod!!")  # raises ValueError
```
.. include:: ../../doc/callable_serialization.md

.. include:: ../../doc/validators.md
.. include:: ../../doc/parsers.md
.. include:: ../../doc/transformers.md

"""

# from .cli_wrapper import CLIWrapper
# from .transformers import transformers
# from .parsers import parsers
# from .validators import validators
# from .util import callable_chain, callable_registry
# from .pre_packaged import get_wrapper

# __all__ = ["CLIWrapper", "get_wrapper", "transformers", "parsers", "validators"]

"""
.. include:: ./util
"""
