# WattIf — common tasks.  Run `make help`.
.DEFAULT_GOAL := help
PY     ?= python3
VENV   := .venv
BIN    := $(VENV)/bin
EXTRAS := dev,ui,pv,data,semantics,api

.PHONY: help install run test api redteam fetch clean

help:  ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-9s\033[0m %s\n", $$1, $$2}'

install:  ## One-line setup: create .venv and install everything
	$(PY) -m venv $(VENV)
	$(BIN)/python -m pip install -U pip
	$(BIN)/pip install -e ".[$(EXTRAS)]"
	@echo "Installed. Now run: make run"

run:  ## Launch the Streamlit app (http://localhost:8501)
	$(BIN)/streamlit run streamlit_app.py

test:  ## Run the test suite
	$(BIN)/pytest

api:  ## Serve the FastAPI app on :8000
	$(BIN)/uvicorn "whatif.api.app:create_app" --factory --port 8000

redteam:  ## Red-team the no-advice guardrail
	$(BIN)/python scripts/redteam_demo.py

fetch:  ## Refresh the cached PVGIS data (needs internet)
	$(BIN)/python scripts/fetch_data.py

clean:  ## Remove the venv and caches
	rm -rf $(VENV) .pytest_cache .ruff_cache src/*.egg-info
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
