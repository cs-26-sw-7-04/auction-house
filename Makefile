.DEFAULT_GOAL := run

build:
	make -C src/vcg 

run: build
	uv run app

