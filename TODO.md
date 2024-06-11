# ToDo

## features

- [x] get current fan speed (RPM/percent/step)
- [x] set desired fan speed (RPM/percent/step)
    - [x] manual
    - [x] lookup table
- [x] get internal temperature
- [x] get sensor temperature
- [x] get/set temperature limits (low/high/crit)
- [x] update status register
    - [x] manually
    - [ ] timer
- [ ] calibrate DC fan
    - [ ] step -> RPM
    - [ ] min step
    - [ ] min RPM
    - [ ] max RPM
- [x] calibrate PWM fan
    - [x] step -> duty cycle + RPM
    - [x] min step/duty cycle
    - [x] min RPM
    - [x] max RPM
- [x] provide unit tests
    - [x] physical device
    - [x] simulated device
- [ ] extract `i2c.i2c_device` as a separate library

## quality of life

- [ ] provide docstrings
- [ ] provide readme
- [ ] provide contribution guide
- [ ] provide editorconfig
- [x] pre-commit hooks
  - [x] validate code (pylint/flake8, ...)
  - [x] verify type hints (mypy, ...)
  - [x] enforce conventional commits
- [x] provide package configuration (setup-tools, poetry, ...)
- [x] automate release management (release-please, commitizen, ...)
- [x] automate compatibility testing (tox+pyenv)
