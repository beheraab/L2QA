.PHONY: update

update: test

check:
	@[ "${VIRTUAL_ENV}" ] || ( echo "Environment variable VIRTUAL_ENV is not set - Check if virtual environment is enabled"; exit 1 )

clean: check
	@echo $@
	pip uninstall -y waldo waldo-devtools waldo-tools kitdb pytest-netbatch SocketMan waldo-environment waldo-jenkins

install:
	pip install -r requirements-dev.txt

develop:
	pip install --no-deps --editable .

test:
	@echo $@
	pytest --cov=src
