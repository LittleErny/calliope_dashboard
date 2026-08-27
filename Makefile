CONDA_COMMAND ?= conda
DASHBOARD_ENV := calliope-dashboard-070

.PHONY: setup test check-model check run generate

setup:
	CONDA_COMMAND=$(CONDA_COMMAND) bash scripts/setup_environments.sh

test:
	$(CONDA_COMMAND) run -n $(DASHBOARD_ENV) pytest -q

check-model:
	$(CONDA_COMMAND) run -n $(DASHBOARD_ENV) python scripts/check_model_environment.py

check: test check-model

run:
	$(CONDA_COMMAND) run --no-capture-output -n $(DASHBOARD_ENV) python app/app.py

generate:
	$(CONDA_COMMAND) run -n $(DASHBOARD_ENV) python models/1_german_scale/calliope_to_netcdf.py
