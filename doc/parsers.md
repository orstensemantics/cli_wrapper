# Parsers

Parsers provide a mechanism to convert the output of a CLI tool into a usable structure. They make use of
`cli_wrapper.util.callable_chain.CallableChain` to be serializable-ish.

## Default Parsers

1. `json`: uses `json.loads` to parse stdout
2. `extract`: extracts data from the raw output, using the args as a list of nested keys.
3. `yaml`: if `ruamel.yaml` is installed, uses `YAML().load_all` to read stdout. If `load_all` only returns one
   document, it returns that document. Otherwise, it returns a list of documents. `pyyaml` is also supported.
4. `dotted_dict`: if `dotted_dict` is installed, converts an input dict or list to a `PreserveKeysDottedDict` or 
   a list of them. This lets you refer to most dictionary keys as `a.b.c` instead of `a["b"]["c"]`.

These can be combined in a list in the `parse` argument to `cli_wrapper.cli_wrapper.CLIWrapper.update_command_`,
allowing the result of the call to be immediately usable.

You can also register your own parsers in `cli_wrapper.parsers.parsers`, which is a 
`cli_wrapper.util.callable_registry.CallableRegistry`.

## Example

```python
from cli_wrapper import CLIWrapper

def skip_lists(result): 
    if result["kind"] == "List":
        return result["items"]
    return result

kubectl = CLIWrapper("kubectl")
# you can use the parser directly, but you won't be able to serialize the
# wrapper to json
kubectl.update_command_(
   "get",
   parse=["json", skip_lists, "dotted_dict"],
   default_flags=["--output", "json"]
)

a = kubectl.get("pods", namespace="kube-system")
assert isinstance(a, list)
b = kubectl.get("pods", a[0].metadata.name, namespace="kube-system")
assert isinstance(b, dict)
assert b.metadata.name == a[0].metadata.name
```
