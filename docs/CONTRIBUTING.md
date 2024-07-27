# Contributing

## quickstart

### one-time setup

__system-wide__

- __install pipx__
- __install build dependencies__ for pyenv
  https://github.com/pyenv/pyenv/wiki#suggested-build-environment

__user-specific__

```SHELL
# install dev tools
pipx install pdm pre-commit tox
pipx inject pdm pdm-autoexport
pipx inject tox virtualenv-pyenv

# OS-independent Python versions
curl https://pyenv.run | bash
pyenv install 3.10
pyenv install 3.11
pyenv install 3.12
```

### repository setup

```SHELL
# install pre-commit hooks
for hook_type in pre-commit commit-msg post-commit pre-push ; do
    pre-commit install --allow-missing-config --hook-type $hook_type
done

# install package dependencies
pdm install
```

### perform unit tests:

```SHELL
pdm run pytest
```

### perform compatibility tests:

```SHELL
tox
```

### use the demo script

```SHELL
pdm run examples/demonstrator.py
pdm run examples/demonstrator.py -v -i 2
```
