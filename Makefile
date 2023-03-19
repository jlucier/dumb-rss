lint:
	black .
	isort .
	ruff .

install-dev:
	pip install .\[dev]
