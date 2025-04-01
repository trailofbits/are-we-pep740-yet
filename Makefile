.PHONY: help
help:
	@echo "make help     -- print this help"
	@echo "make generate -- regenerate the json"

.PHONY: generate
generate:
	wget https://hugovk.github.io/top-pypi-packages/top-pypi-packages.min.json -O top-pypi-packages.json
	./generate.py

.PHONY: live
live:
	uv run --no-project python -m http.server -b 0.0.0.0 1337

