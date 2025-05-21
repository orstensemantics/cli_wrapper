# Callable serialization

Argument validation and parser configuration are not straightforward to serialize. To get around this, CLI Wrapper uses
`CallableRegistry` and `CallableChain`. These make it somewhat more straightforward to create more serializable wrapper
configurations.

## TL;DR
- Functions that perform validation, argument transformation, or output parsing are registered with a name in a
  `CallableRegistry`
- `CallableChain` resolves a serializable structure to a sequence of calls to those functions
  - a string refers to a function, which will be called directly
  - a dict is expected to have one key (the function name), with a value that provides additional configuration:
    - a string as a single positional arg
    - a list of positional args
    - a dict of kwargs (the key "args" will be popped and used as positional args if present)
  - a list of the previous two


- A list of validators is treated as a set of conditions which must be true
- A list of parsers will be piped together in sequence
- Transformers receive an arg name and value, and return another arg and value. They are not chained.

## Implementation

Here's how these work:

### `CallableRegistry`

Callable registries form the basis of serializing callables by mapping strings to functions. If you are doing custom
parsers and validators and you want these to be serializable, you will use their respective callable registries to
associate the code with the serializable name.

```python

def greater_than(a, b):
  return a > b


registry = CallableRegistry(
  {
    "core" = {}
  }
)
registry.register("gt", greater_than)

x = registry.get("gt", [2])

assert(not x(1))
assert(x(3))
```

### `CallableChain`

A callable chain is a serializable structure that gets converted to a sequence of calls to things in a
`cli_wrapper.util.callable_registry.CallableRegistry`. It is an abstract base class, and so shouldn't be created directly; subclasses are expected to
implement `__call__`. We'll use the `.validators.Validator` class as an example. `validators` is a `CallableRegistry` with all of
the base validators (`is_dict`, `is_list`, `is_str`, `startswith`...)

```python
# Say we have these validators that we want to run:
def every_letter_is(v, l):
    return all((x == l.lower()) or (x == l.upper()) for x in v)

validators.register("every_letter_is", every_letter_is)

my_validation = ["is_str", {"every_letter_is": "a"}]

straight_as = Validator(my_validation)
assert(straight_as("aaaaAAaa"))
assert(not straight_as("aaaababa"))
```

`Validator.__call__` just checks that every validation returns true. Elsewhere, `Parser` pipes inputs in sequence:

```yaml
parser:
  - yaml
  - extract: result 
```

This would first parse the output as yaml and then extract the "result" key from the dictionary returned by the yaml
step.