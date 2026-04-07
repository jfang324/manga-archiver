.PHONY: test report lint fix format typecheck clean check report-utils report-workers report-widgets report-integrations

test:
	poetry run coverage run -m pytest

report:
	poetry run coverage report -m

report-utils:
	poetry run coverage report --include="*/utils/*"

report-workers:
	poetry run coverage report --include="*/workers/*"

report-widgets:
	poetry run coverage report --include="*/widgets/*"

report-integrations:
	poetry run coverage report --include="*/integrations/*"

fix:
	poetry run ruff check --fix .

format:
	poetry run ruff format .

typecheck:
	poetry run pyright

check: fix format typecheck
