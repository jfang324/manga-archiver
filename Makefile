.PHONY: test report lint fix format typecheck clean check

test:
	poetry run coverage run -m pytest

report:
	poetry run coverage report -m

fix:
	poetry run ruff check --fix .

format:
	poetry run ruff format .

typecheck:
	poetry run pyright

check: fix format typecheck
