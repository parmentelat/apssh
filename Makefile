include Makefile.pypi

##############################
tags:
	git ls-files | xargs etags

.PHONY: tags

##########
# always running tests through nose makes life easier
tests test:
	nosetests tests/test_*.py -s

.PHONY: tests test

########## sphinx
sphinx doc html:
	$(MAKE) -C sphinx html

sphinx-clean:
	$(MAKE) -C sphinx clean

all-sphinx: readme-clean readme sphinx

.PHONY: sphinx doc html sphinx-clean all-sphinx

##########
pyfiles:
	@git ls-files | grep '\.py$$' | grep -v '/conf.py$$'

pep8:
	$(MAKE) pyfiles | xargs flake8 --max-line-length=80 --exclude=__init__.py

pylint:
	$(MAKE) pyfiles | xargs pylint

.PHONY: pep8 pylint pyfiles

########## actually install
infra:
	apssh -t r2lab.infra pip3 install --upgrade apssh
check:
	apssh -t r2lab.infra apssh --version

.PHONY: infra check
