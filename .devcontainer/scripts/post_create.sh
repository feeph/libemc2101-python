#!/bin/bash
#
# perform necessary post-checkout actions
#
# this script will be executed with containerWorkspaceFolder
# (/workspaces/<repositoryname>) as the current directory

set -e

# permissions are known to be messed up in devcontainers, persuade git to
# ignore them (without this pre-commit will fail to install its hook)
git config --global --add safe.directory /workspaces/libi2c-emc2101-python

pdm install

pre-commit install --allow-missing-config -t pre-commit
pre-commit install --allow-missing-config -t commit-msg
pre-commit install --allow-missing-config -t post-commit
pre-commit install --allow-missing-config -t pre-push
