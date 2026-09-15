.PHONY: test

test:
	@for f in cli/test_*.py; do echo "$$f"; python3 "$$f" || exit 1; done
