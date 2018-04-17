########## for uploading onto pypi
# this assumes you have an entry 'pypi' in your .pypirc
# see pypi documentation on how to create .pypirc

LIBRARY = apssh

VERSION = $(shell python3 -c "from $(LIBRARY).version import __version__; print(__version__)")
VERSIONTAG = $(LIBRARY)-$(VERSION)
GIT-TAG-ALREADY-SET = $(shell git tag | grep '^$(VERSIONTAG)$$')
# to check for uncommitted changes
GIT-CHANGES = $(shell echo $$(git diff HEAD | wc -l))

# run this only once the sources are in on the right tag
pypi:
	@if [ $(GIT-CHANGES) != 0 ]; then echo "You have uncommitted changes - cannot publish"; false; fi
	@if [ -n "$(GIT-TAG-ALREADY-SET)" ] ; then echo "tag $(VERSIONTAG) already set"; false; fi
	@if ! grep -q ' $(VERSION)' CHANGELOG.md ; then echo no mention of $(VERSION) in CHANGELOG.md; false; fi
	@echo "You are about to release $(VERSION) - OK (Ctrl-c if not) ? " ; read _
	git tag $(VERSIONTAG)
	./setup.py sdist upload -r pypi

# it can be convenient to define a test entry, say testpypi, in your .pypirc
# that points at the testpypi public site
# no upload to build.onelab.eu is done in this case
# try it out with
# pip install -i https://testpypi.python.org/pypi $(LIBRARY)
# dependencies need to be managed manually though
testpypi:
	./setup.py sdist upload -r testpypi

##############################
tags:
	git ls-files | xargs etags

.PHONY: tags

##########
# xxx in theory this would do the trick
# python3 -m unittest discover tests
# but results in this error:
# AttributeError: module '__main__' has no attribute 'discover'
tests test:
	python3 -m unittest

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
