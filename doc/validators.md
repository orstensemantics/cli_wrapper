from curses import wrapper

# Validators

Validators are used to validate argument values. They are implemented as a
`cli_wrapper.util.callable_chain.CallableChain` for serialization. Callables in the chain are called with the value
sequentially, stopping at the first callable that returns False.

## Default Validators

The default validators are:

- `is_dict`
- `is_list`
- `is_str`
- `is_str_or_list`
- `is_int`
- `is_float`
- `is_bool`
- `is_path` - is a `pathlib.Path`
- `is_alnum` - is alphanumeric
- `is_alpha` - is alphabetic
- `starts_alpha` - first digit is a letter
- `startswith` - checks if the string starts with a given prefix

## Custom Validators

You can register your own validators in `cli_wrapper.validators.validators`:

1. Takes at most one positional argument
2. When configuring the validator, additional arguments can be supplied using a dictionary:

```python
wrapper.update_command_("cmd", validators={"arg":["is_str", {"startswith": {"prefix": "prefix"}}]})
# or
wrapper.update_command_("cmd", validators={"arg": ["is_str", {"startswith": "prefix"}]})
```
## Example

```python
from cli_wrapper import CLIWrapper
from cli_wrapper.validators import validators

def is_alnum_or_dash(value):
    return all(c.isalnum() or c == "-" for c in value)
validators.register("is_alnum_or_dash", is_alnum_or_dash)

kubectl = CLIWrapper("kubectl")
# 1 refers to the first positional argument, so in `kubectl.get("pods", "my-pod")` it would refer to `"my-pod"`
kubectl.update_command_("get", validators={
 1: ["is_str", "is_alnum_or_dash", "starts_alpha"],
})

assert kubectl.get("pods", "my-pod")
threw = False
try:
    kubectl.get("pods", "level-9000-pod!!")
except ValueError:
    threw = True
assert threw
```