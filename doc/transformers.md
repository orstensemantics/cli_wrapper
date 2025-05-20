# Transformers

Argument transformers receive an argument (either a numbered positional argument or a string keywork argument/flag) and
a value. They return a tuple of argument and value that replace the original.

The main transformer used by cli-wrapper is `snake2kebab`, which converts a `an_argument_like_this` to
`an-argument-like-this` and returns the value unchanged. This is the default transformer for all keyword arguments.

Transformers are added to a callable registry, so they can be refernced as a string after they're registered.
Transformers are not currently chained.

## Other possibilities for transformers

### 1. Write dictionaries to files and return a flag referencing a file

Consider a command like `kubectl create`: the primary argument is a filename or list of files. Say you have your 
manifest to create as a dictionary:

```python
from pathlib import Path
from ruamel.yaml import YAML
from cli_wrapper import transformers, CLIWrapper

manifest_count = 0
base_filename = "my_manifest"
base_dir = Path()
y = YAML()
def write_manifest(manifest: dict | list[dict]):
    global manifest_count
    manifest_count += 1
    file = base_dir / f"{base_filename}_{manifest_count}.yaml"
    with file.open("w") as f:
        if isinstance(manifest, list):
            y.dump_all(manifest, f)
        else:
            y.dump(manifest, f)
    return file.as_posix()

def manifest_transformer(arg, value, writer=write_manifest):
    return "filename", writer(value)

transformers.register("manifest", manifest_transformer)

# If you had different writer functions (e.g., different base name), you could register those as partials:
from functools import partial
transformers.register("other_manifest", partial(manifest_transformer, writer=my_other_writer))

kubectl = CLIWrapper('kubectl')
kubectl.update_command_("create", args={"data": {"transformer": "manifest"}})

# will write the manifest to "my_manifest_1.yaml" and execute `kubectl create -f my_manifest_1.yaml`
kubectl.create(data=my_kubernetes_manifest)
```

## Possible future changes

- it might make sense to make transformers a [`CallableChain`](callable_serialization.md#callablechain) similar to parser so a sequence of things can be done on an arg
- it might also make sense to support transformers that break individual args into multiple args with separate values
