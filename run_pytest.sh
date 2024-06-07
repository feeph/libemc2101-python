#!/bin/bash
#
# initialize virtual environment (if needed) and run unittests
# (assumes Python 3.11 is used)
#
# usage:
#   ./run_pytest.sh
#   TEST_EMC2101_CHIP=y ./run_pytest.sh
#   TEST_EMC2101_CHIP=y TEST_EMC2101_SENSOR=y ./run_pytest.sh

if [ ! -d .venv ] ; then
    python3 -m venv .venv --prompt="`python3 --version|cut -d'.' -f1,2`"
    .venv/bin/pip install --upgrade pip
    .venv/bin/pip install -r requirements.txt
fi

PYTHONPATH=src:.venv/lib/python3.11/site-packages/ pytest tests/
