# ------------------------------------------------------------------------------
# Makefile for zhmc-ansible-modules project
#
# Basic prerequisites for running this Makefile, to be provided manually:
#   One of these OS platforms:
#     Windows with CygWin
#     Linux (any)
#     OS-X
#   These commands on all OS platforms:
#     make (GNU make)
#     bash
#     rm, mv, find, tee, which
#   These commands on all OS platforms in the active Python environment:
#     python (or python3 on OS-X)
#     pip (or pip3 on OS-X)
#     twine
#   These commands on Linux and OS-X:
#     uname
# Environment variables:
#   PYTHON_CMD: Python command to use (OS-X needs to distinguish Python 2/3)
#   PIP_CMD: Pip command to use (OS-X needs to distinguish Python 2/3)
#   PACKAGE_LEVEL: minimum/latest - Level of Python dependent packages to use
# Additional prerequisites for running this Makefile are installed by running:
#   make develop
# ------------------------------------------------------------------------------

# Python / Pip commands
ifndef PYTHON_CMD
  PYTHON_CMD := python
endif
ifndef PIP_CMD
  PIP_CMD := pip
endif

# Package level
ifndef PACKAGE_LEVEL
  PACKAGE_LEVEL := latest
endif
ifeq ($(PACKAGE_LEVEL),minimum)
  pip_level_opts := -c minimum-constraints.txt
else
  ifeq ($(PACKAGE_LEVEL),latest)
    pip_level_opts := --upgrade
  else
    $(error Error: Invalid value for PACKAGE_LEVEL variable: $(PACKAGE_LEVEL))
  endif
endif

# Determine OS platform make runs on
ifeq ($(OS),Windows_NT)
  PLATFORM := Windows
else
  # Values: Linux, Darwin
  PLATFORM := $(shell uname -s)
endif

# Name of this package on Pypi
package_name := zhmc_ansible_modules
package_name_under := zhmc_ansible_modules

# Package version (full version, including any pre-release suffixes, e.g. "0.2.1.dev42")
package_version := $(shell $(PIP_CMD) show $(package_name) | grep "Version:" | sed -e 's/Version: *\(.*\)$$/\1/')

# Python major version
python_major_version := $(shell $(PYTHON_CMD) -c "import sys; sys.stdout.write('%s'%sys.version_info[0])")

# Python major+minor version
python_mn_version := $(shell $(PYTHON_CMD) -c "import sys; sys.stdout.write('%s%s'%(sys.version_info[0],sys.version_info[1]))")

# Build directory
build_dir = build

# Directory tree with our Ansible module source files
ansible_dir := ansible

# Directory with the Ansible zhmc module
ansible_module_dir := $(ansible_dir)/modules/zhmc
ansible_module_files := $(wildcard $(ansible_module_dir)/zhmc_*.py)

# Our Ansible module source files
ansible_py_files := \
    $(wildcard $(ansible_dir)/*.py) \
    $(wildcard $(ansible_dir)/*/*.py) \
    $(wildcard $(ansible_dir)/*/*/*.py) \

# Directory for the generated distribution files
dist_build_dir := $(build_dir)/dist

# Distribution archives (as built by setup.py)
bdist_file := $(dist_build_dir)/$(package_name_under)-$(package_version)-py2.py3-none-any.whl
sdist_file := $(dist_build_dir)/$(package_name)-$(package_version).tar.gz

# Files the distribution archive depends upon.
dist_dependent_files := \
    README.rst \
    requirements.txt \
    $(wildcard *.py) \
    $(wildcard $(package_name)/*.py) \

# Directory for documentation (with Makefile)
doc_dir := docs
doc_gen_dir := $(doc_dir)/gen

# Directory for generated documentation
doc_build_dir := $(build_dir)/docs

# Documentation generator command
sphinx := sphinx-build
sphinx_conf_dir := $(doc_dir)
sphinx_opts := -v -d $(doc_build_dir)/doctrees -c $(sphinx_conf_dir)

# Dependents for Sphinx documentation build
doc_dependent_files := \
    $(sphinx_conf_dir)/conf.py \
    $(wildcard $(doc_dir)/*.rst) \
    $(ansible_py_files) \

# Flake8 config file
flake8_rc_file := setup.cfg

# FLake8 log file
flake8_log_file := flake8_$(python_mn_version).log

# Source files for check (with Flake8)
check_py_files := \
    setup.py \
    $(ansible_py_files) \
    $(wildcard tests/*.py) \
    $(wildcard tests/*/*.py) \
    $(wildcard tests/*/*/*.py) \
    $(wildcard tools/*.py) \

# Test log file
test_log_file := test_$(python_mn_version).log

ifdef TESTCASES
pytest_opts := -k $(TESTCASES)
else
pytest_opts :=
endif

# Location of local clone of Ansible project's Git repository.
# Note: For now, that location must have checked out the 'zhmc-fixes' branch
# from our fork of the Ansible repo. Create that with:
# git clone https://github.com/andy-maier/ansible.git --branch zhmc-fixes ../ansible
ansible_repo_dir := ../ansible

# Documentation-related stuff from Ansible project
ansible_repo_template_dir := $(ansible_repo_dir)/docs/templates
ansible_repo_lib_dir := $(ansible_repo_dir)/lib

ansible_repo_plugin_formatter := $(ansible_repo_dir)/docs/bin/plugin_formatter.py
ansible_repo_plugin_template := $(ansible_repo_template_dir)/plugin.rst.j2

ansible_repo_keyword_dumper := $(ansible_repo_dir)/docs/bin/dump_keywords.py
ansible_repo_keyword_template := $(ansible_repo_template_dir)/playbooks_keywords.rst.j2
ansible_repo_keyword_desc := $(ansible_repo_dir)/docs/docsite/keyword_desc.yml

# validate-modules tool from Ansible project
ansible_repo_validate_modules := $(ansible_repo_dir)/test/sanity/validate-modules/validate-modules
validate_modules_log_file := validate.log
validate_modules_exclude_pattern := (E101|E105|E106)

# No built-in rules needed:
.SUFFIXES:

.PHONY: help
help:
	@echo 'Makefile for $(package_name) project'
	@echo 'Package version will be: $(package_version)'
	@echo 'Currently active Python environment: Python $(python_mn_version)'
	@echo 'Valid targets are:'
	@echo '  setup      - Set up the development environment'
	@echo '  dist       - Build the distribution files in: $(dist_build_dir)'
	@echo '  docs       - Build the documentation in: $(doc_build_dir)'
	@echo '  check      - Run Flake8 and Ansible validate-modules'
	@echo '  test       - Run unit tests (and test coverage) and save results in: $(test_log_file)'
	@echo '               Env.var TESTCASES can be used to specify a py.test expression for its -k option'
	@echo '  all        - Do all of the above'
	@echo '  install    - Install package in active Python environment'
	@echo '  uninstall  - Uninstall package from active Python environment'
	@echo '  upload     - Upload the package to PyPI'
	@echo '  clobber    - Remove any produced files'
	@echo '  linkcheck  - Check links in documentation'
	@echo 'Environment variables:'
	@echo '  PACKAGE_LEVEL="minimum" - Install minimum version of dependent Python packages'
	@echo '  PACKAGE_LEVEL="latest" - Default: Install latest version of dependent Python packages'
	@echo '  PYTHON_CMD=... - Name of python command. Default: python'
	@echo '  PIP_CMD=... - Name of pip command. Default: pip'

.PHONY: _pip
_pip:
	@echo 'Installing/upgrading pip, setuptools and wheel with PACKAGE_LEVEL=$(PACKAGE_LEVEL)'
	$(PIP_CMD) install $(pip_level_opts) pip
	$(PIP_CMD) install $(pip_level_opts) setuptools
	$(PIP_CMD) install $(pip_level_opts) wheel

.PHONY: setup
setup: _pip requirements.txt dev-requirements.txt os_setup.sh $(ansible_repo_dir)
	@echo 'Setting up the development environment with PACKAGE_LEVEL=$(PACKAGE_LEVEL)'
	bash -c './os_setup.sh'
	$(PIP_CMD) install $(pip_level_opts) -r dev-requirements.txt
	@echo '$@ done.'

.PHONY: dist
dist: $(bdist_file) $(sdist_file)
	@echo '$@ done.'

.PHONY: docs
docs: $(doc_build_dir)/html/index.html
	@echo '$@ done.'

.PHONY: check
check: $(flake8_log_file) $(validate_modules_log_file)
	@echo '$@ done.'

.PHONY: test
test: $(test_log_file)
	@echo '$@ done.'

.PHONY: all
all: setup dist docs check test
	@echo '$@ done.'

.PHONY: install
install: _pip
	@echo 'Installing package $(package_name) and its requirements with PACKAGE_LEVEL=$(PACKAGE_LEVEL)'
	$(PIP_CMD) install $(pip_level_opts) .
	@echo "Installed $(package_name) in $$(cd tests && dirname $$(python -c 'from ansible.modules import zhmc; print(zhmc.__file__)'))"
	@echo 'Done: Installed $(package_name) into current Python environment.'
	@echo '$@ done.'

.PHONY: uninstall
uninstall:
	bash -c '$(PIP_CMD) show $(package_name) >/dev/null; rc=$$?; if [[ $$rc == 0 ]]; then $(PIP_CMD) uninstall -y $(package_name); fi'
	@echo '$@ done.'

.PHONY: upload
upload: $(bdist_file) $(sdist_file)
ifeq (,$(findstring .dev,$(package_version)))
	@echo '==> This will upload $(package_name) version $(package_version) to PyPI!'
	@echo -n '==> Continue? [yN] '
	@bash -c 'read answer; if [[ "$$answer" != "y" ]]; then echo "Aborted."; false; fi'
	twine upload $(bdist_file) $(sdist_file)
	@echo 'Done: Uploaded $(package_name) version to PyPI: $(package_version)'
	@echo '$@ done.'
else
	@echo 'Error: A development version $(package_version) of $(package_name) cannot be uploaded to PyPI!'
	@false
endif

.PHONY: clobber
clobber:
	rm -Rf .cache $(package_name_under).egg-info .eggs $(build_dir) $(doc_gen_dir) htmlcov .tox
	rm -f MANIFEST MANIFEST.in AUTHORS ChangeLog .coverage flake8_*.log test_*.log validate.log
	find . -name "*.pyc" -delete -o -name "__pycache__" -delete -o -name "*.tmp" -delete -o -name "tmp_*" -delete
	@echo 'Done: Removed all build products to get to a fresh state.'
	@echo '$@ done.'

$(bdist_file) $(sdist_file): Makefile setup.py $(dist_dependent_files)
ifneq ($(PLATFORM),Windows)
	rm -Rf $(package_name_under).egg-info .eggs
	mkdir -p $(dist_build_dir)
	$(PYTHON_CMD) setup.py sdist -d $(dist_build_dir) bdist_wheel -d $(dist_build_dir) --universal
	@echo 'Done: Created distribution files: $@'
else
	@echo 'Error: Creating distribution archives requires to run on Linux or OS-X'
	@false
endif

.PHONY: linkcheck
linkcheck: $(doc_build_dir)/linkcheck/output.txt
	@echo '$@ done.'

$(ansible_repo_dir):
	@echo 'Cloning our fork of the Ansible repo into: $@'
	git clone https://github.com/andy-maier/ansible.git --branch zhmc-fixes $@

$(doc_gen_dir)/list_of_all_modules.rst: $(ansible_repo_plugin_formatter) $(ansible_repo_plugin_template) $(ansible_py_files)
	mkdir -p $(doc_gen_dir)
	PYTHONPATH=$(ansible_repo_lib_dir) $(ansible_repo_plugin_formatter) -vv --type=rst --template-dir=$(ansible_repo_template_dir) --module-dir=$(ansible_module_dir) --output-dir=$(doc_gen_dir)/

$(doc_gen_dir)/playbooks_keywords.rst: $(ansible_repo_keyword_dumper) $(ansible_repo_keyword_template) $(ansible_repo_keyword_desc)
	mkdir -p $(doc_gen_dir)
	PYTHONPATH=$(ansible_repo_lib_dir) $(ansible_repo_keyword_dumper) --template-dir=$(ansible_repo_template_dir) --docs-source=$(ansible_repo_keyword_desc) --output-dir=$(doc_gen_dir)/

#staticmin:
#	cat _themes/srtd/static/css/theme.css | sed -e 's/^[    ]*//g; s/[      ]*$$//g; s/\([:{;,]\) /\1/g; s/ {/{/g; s/\/\*.*\*\///g; /^$$/d' | sed -e :a -e '$$!N; s/\n\(.\)/\1/; ta' > _themes/srtd/static/css/theme.min.css

$(doc_build_dir)/html/index.html: Makefile $(doc_dependent_files) $(doc_gen_dir)/list_of_all_modules.rst $(doc_gen_dir)/playbooks_keywords.rst
	rm -fv $@
	mkdir -p $(doc_build_dir)
	$(sphinx) -b html $(sphinx_opts) $(doc_dir) $(doc_build_dir)/html
	@echo "Done: Created the HTML pages with top level file: $@"

$(doc_build_dir)/linkcheck/output.txt: Makefile $(doc_dependent_files) $(doc_gen_dir)/list_of_all_modules.rst $(doc_gen_dir)/playbooks_keywords.rst
	$(sphinx) -b linkcheck $(sphinx_opts) $(doc_dir) $(doc_build_dir)/linkcheck
	@echo
	@echo "Done: Look for any errors in the above output or in: $@"

$(flake8_log_file): Makefile $(flake8_rc_file) $(check_py_files)
	rm -f $@
	bash -c 'set -o pipefail; flake8 $(check_py_files) 2>&1 |tee $@.tmp'
	mv -f $@.tmp $@
	@echo 'Done: Flake8 checker succeeded'

$(validate_modules_log_file): Makefile $(ansible_module_files)
	rm -f $@
	bash -c 'PYTHONPATH=$(ansible_repo_lib_dir) $(ansible_repo_validate_modules) $(ansible_module_files) 2>&1 |grep -v -E "$(validate_modules_exclude_pattern)" |tee $@.tmp'
	if [[ -n "$$(cat $@.tmp)" ]]; then false; fi
	mv -f $@.tmp $@
	@echo 'Done: Ansible validate-modules checker succeeded'

# We cd into tests in order to find the installed ansible module (in site-packages)
# and not our ansible subdirectory. As a consequence, we need to install our Ansible
# module (into site-packages).
$(test_log_file): Makefile $(check_py_files)
	@echo "Note: This tests the *installed* Ansible modules; make sure you have run 'make install'"
	rm -f $@
	bash -c 'set -o pipefail; cd tests; PYTHONWARNINGS=default py.test --cov $$(dirname $$(python -c "from ansible.modules import zhmc; print(zhmc.__file__)")) --cov-config ../.coveragerc --cov-report=html:../htmlcov $(pytest_opts) -s 2>&1 |tee ../$@.tmp'
	mv -f $@.tmp $@
	@echo 'Done: Created test log file: $@'