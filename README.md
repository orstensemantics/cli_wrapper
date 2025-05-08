# CLI Wrapper

![Codecov](https://img.shields.io/codecov/c/github/orstensemantics/cli_wrapper)
![PyPI - License](https://img.shields.io/pypi/l/cli_wrapper)
![PyPI - Version](https://img.shields.io/pypi/v/cli_wrapper)


CLI Wrapper uses subprocess to wrap external CLI tools and present an interface that looks more like a python class. CLI
commands become methods on the class, positional arguments and flags become args and kwargs respectively. It
supports input validation and output parsing.

## Why would you use this?

CLI tools wrap a lot of functionaility, and they tend to do it in a way that's simpler and more stable than the
underlying API. So if you're writing some DevOps tooling that interacts with the Kubernetes API, for example:

- you could pull in the kubernetes client library, introduce a fast-moving dependency, deal with all of your kube
  resources one at a time, and still not have a builder for CRDs your operators expose
- you could use this wrapping kubectl, use dicts, templated manifest files, or serializable objects.
  You get the same functionality, but now you only need to update your manifests when the api changes. Kubernetes
  version changes are punted to kubectl. If you manage your manifests in a smart way, you will have decoupled your code
  from the underlying kubernetes version.

An enormous number of things in the kubernetes ecosystem provide cli tools that are stable and first-class, but
libraries favour Go and Python bindings are often non-existent or badly maintained. With this, you can leave all of that behind.
Want to tie in the latest Cilium feature? Want to do some fancy Argo automation? No problem!

If you accept this argument, then the next question is: why not just use subprocess? I think the example code speaks for
itself. You get an interface for cli arguments that behaves just like a python class. How things are parsed and what
gets returned are hidden in the wrapper config, so your business logic is all business. 

## Example

```python
from cli_wrapper import CLIWrapper

# this assumes kubectl is in your path; otherwise provide the full path 
kubectl = CLIWrapper("kubectl")
# by default, this will translate to `kubectl get pods --namespace default`, and it will return the text output
kubectl.get("pods", namespace="default")
# you can refine this by defining the command explicitly:
kubectl.update_command_("get", default_flags={"output": "json"}, parse=["json", "dotted_dict"])
# (the trailing '_' is to avoid collisions with a cli command)
a = kubectl.get("pods", namespace="kube-system")
print(a.items[0].metadata.name)  # prints a pod name


# you can do your own parsing:
def skip_lists(result):
    if result["kind"] == "List":
        return result["items"]
    return result


kubectl.update_command_("get", default_flags={"output": "json"}, parse=["json", skip_lists, "dotted_dict"])
a = kubectl.get("pods", namespace="kube-system")
assert isinstance(a, list)
a = kubectl.get("pods", a[0].metadata.name, namespace="kube-system")
assert isinstance(a, dict)

# If you want async:
kubectl.async_ = True  # or use CLIWrapper("kubectl", async_=True)
a = await kubectl.get("pods", namespace="kube-system")

# you can also set env vars where that's helpful:
kubectl.env = {
    "KUBECONFIG": "/home/user/.kube/config",
    "KUBECTL_CONTEXT": "my-other-cluster",
}
a = await kubectl.get("pods", namespace="kube-system")  # use the context from the env vars
```

## Installation

Requires python 3.10 or later.

```bash
pip install cli-wrapper # for just the wrapper
pip install ruamel.yaml # for yaml support
pip install dotted_dict # for dotted_dict support shown above
```

## Todo

- [x] build and publish to PyPI
- [x] Core wrapper functionality, trusting mode by default
    - [x] args and kwargs mapping to positional and flag arguments
    - [x] support for default flags
    - [x] support for argument transformation (e.g., `kubectl.create(a_dict)` would write that dict to a file and
      become `kubectl.create(filename=a_dict_filename)`)
      - [ ] document how to do this
    - [x] support for input validation
      - possibly wrap this into argument transformation
- [x] Support for parsing output
    - [ ] better default support for extracting output (e.g., if `result["kind"] == "List"`, return `result["items"]`
      instead of the whole dict)
      - We can already do this by putting a function in the parse list, but it would be nice to make this serializable
- [ ] Custom error handling
- [ ] Nested wrappers (e.g., `helm.repos.list()` instead of `helm.repos('list')`)]
  - currently doing helm.repos_list() from help parser
- [ ] Tool to create configuration dictionaries by parsing help output recursively
    - [x] golang flag style help/usage
    - [ ] argparse style
- [ ] Configuration dictionaries for common tools
    - [x] kubectl
    - [x] helm
    - [ ] docker
    - [x] cilium