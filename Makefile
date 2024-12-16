all: doc

##########
# nose no longer maintained
tests:
	pytest

.PHONY: tests

########## sphinx
doc:
	$(MAKE) -C sphinx html

doc-clean:
	$(MAKE) -C sphinx clean

.PHONY: doc doc-clean

##########
pyfiles:
	@git ls-files | grep '\.py$$' | grep -v '/conf.py$$'

pep8:
	$(MAKE) pyfiles | xargs flake8 --max-line-length=80 --exclude=__init__.py

pylint:
	$(MAKE) pyfiles | xargs pylint

.PHONY: pyfiles pep8 pylint

########## actually install
infra:
	apssh -t r2lab.infra pip install --upgrade apssh
check:
	apssh -t r2lab.infra apssh --version

.PHONY: infra check
