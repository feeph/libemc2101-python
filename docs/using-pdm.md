# Using PDM

full documentation: https://pdm-project.org/

install PDM

```SHELL
pipx install pdm
pdm config strategy.save compatible
pdm plugin add pdm-autoexport
```

## initialization

use the repository & install required dependencies

```SHELL
git checkout https://github.com/feeph/libi2c-emc2101-python.git
cd libi2c-emc2101-python
pdm install
```

## working with the code

run a script

```SHELL
pdm run scripts/calibrate_pwm_fan.py
```

testing

```SHELL
# execute specific tools within PDM
pdm run autopep8 --diff --ignore-local-config -r src/
pdm run flake8 src/ tests/
pdm run mypy src/ tests/
pdm run pytest

# execute all predefined tests (incl. multiple Python versions)
#   it is possible to run tox in PDM but we're not going to do that since
#   the combination of pdm + pyenv + tox is problematic even with tox-pdm
tox
```

## manage dependencies

add a dependency

```SHELL
pdm add "adafruit-board-toolkit >= 1.1.0"
```

add development-only dependencies

```SHELL
pdm add --dev --group=test autopep8 flake8 mypy pytest pytest-sugar
```

update dependencies

_(since we configured `tool.pdm.autoexport` in pyproject.toml the requirements.txt file will be updated as well and kept in sync with pdm.lock)_

```SHELL
pdm update
pdm update --dev
```

## build and publish

build the package

```SHELL
pdm build
```

publish an existing build

```SHELL
pdm build --no-build
```

build and publish in a single step

```SHELL
pdm build
```
