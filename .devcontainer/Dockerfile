# syntax=docker/dockerfile:1

#
# prepare docker image for development (PDM) and compatibility testing (tox)
#

FROM ubuntu:24.04

WORKDIR /

# --------------------------------------------------------------------------
# as superuser
# --------------------------------------------------------------------------

# automatically exit on error (for heredocs)
SHELL ["/bin/bash", "-e", "-c"]

# packages
#  - bash                 (for user shell & pipx)
#  - build requirements   (for pyenv)
#  - git, pipx            (for development)
ENV PACKAGES="bash build-essential curl git libbz2-dev libffi-dev liblzma-dev libncursesw5-dev libreadline-dev libsqlite3-dev libssl-dev libxml2-dev libxmlsec1-dev pipx tk-dev xz-utils zlib1g-dev"

# always use 1000:1000 for maximum compatibility
# (on Ubuntu images that implies the ubuntu user)

# install required packages & create an unprivileged user account
RUN <<__EOF__
  apt update
  apt upgrade -y
  apt install -y ${PACKAGES}
  apt autoremove

  #mkdir /workspaces
  #chown dev:dev /workspaces
__EOF__

# --------------------------------------------------------------------------
# as non-privileged user
# --------------------------------------------------------------------------

USER ubuntu:ubuntu

# update home variable and current directory
ENV HOME=/home/ubuntu
WORKDIR $HOME

# avoid error:
#   PermissionError: [Errno 13] Permission denied: '/usr/local/py-utils/venvs/pdm'
ENV PIPX_HOME="$HOME/.local/pipx"

RUN pipx ensurepath

# install and configure pyenv
# https://github.com/pyenv/pyenv
#RUN git clone https://github.com/pyenv/pyenv.git ~/.pyenv && echo -e "\n# configure pyenv settings\nexport PYENV_ROOT=\"\$HOME/.pyenv\"\n[[ -d \$PYENV_ROOT/bin ]] && export PATH=\"\$PYENV_ROOT/bin:\$PATH\"\neval \"\$(pyenv init -)\"\neval \"\$(pyenv virtualenv-init -)\"" >> ~/.bashrc
RUN git clone https://github.com/pyenv/pyenv.git ~/.pyenv && echo -e "\n# configure pyenv settings\nexport PYENV_ROOT=\"\$HOME/.pyenv\"\n[[ -d \$PYENV_ROOT/bin ]] && export PATH=\"\$PYENV_ROOT/bin:\$PATH\"\neval \"\$(pyenv init -)\"" >> ~/.bashrc

# configure bash as an interactive shell to make '. ~/.bashrc' work
#  - interactive
#  - enable automatic exit on error
#  - enable job control
SHELL ["/bin/bash", "-i", "-e", "-c"]

# install dev tooling
#   - PDM <https://pdm-project.org/>
#   - pre-commit <https://pre-commit.com/>
#   - tox <https://pypi.org/project/tox/>
RUN <<"__EOT__"
  pipx install pdm pre-commit tox
  pipx inject tox virtualenv-pyenv
  pdm plugin add pdm-autoexport
  pdm config strategy.save compatible
__EOT__

# provide desired Python versions for compatibility testing (used by tox)
# (ideally compiled in parallel but didn't get it to work)
#
# lifetime: https://devguide.python.org/versions/
RUN <<"__EOT__"
  # start a background process for each Python version
  # (pyenv is mostly single-thread and the can run in parallel)
  for version in 3.8 3.9 3.10 3.11 3.12 ; do
    PYTHON_CONFIGURE_OPTS='--enable-optimizations --with-lto' PYTHON_CFLAGS='-march=native -mtune=native' pyenv install $version 2> pyenv_python-${version}.log
  done
__EOT__
