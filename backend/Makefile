# Forward every target to the root Makefile.
.DEFAULT_GOAL := help

.PHONY: help
help:
	@$(MAKE) --no-print-directory -C .. help

.DEFAULT:
	@$(MAKE) --no-print-directory -C .. $@
