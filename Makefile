PREFIX ?= $(HOME)/.local

.PHONY: install test lint

install:
	PREFIX="$(PREFIX)" ./install.sh

test:
	python3 -m unittest discover -s tests -v

lint:
	python3 -m py_compile bin/osc52-tee
	sh -n bin/ossh
	sh -n install.sh
