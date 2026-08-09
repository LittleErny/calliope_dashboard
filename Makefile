CONDA_COMMAND ?= conda
DASHBOARD_ENV := calliope-dashboard-0610
MODEL_ENV := calliope-model-0610

.PHONY: setup test check-model check run generate

setup:
	CONDA_COMMAND=$(CONDA_COMMAND) bash scripts/setup_environments.sh

test:
	$(CONDA_COMMAND) run -n $(DASHBOARD_ENV) pytest -q

check-model:
	$(CONDA_COMMAND) run -n $(MODEL_ENV) python scripts/check_model_environment.py

check: test check-model

run:
	$(CONDA_COMMAND) run -n $(DASHBOARD_ENV) python app/app.py

generate:
	$(CONDA_COMMAND) run -n $(MODEL_ENV) python models/mainkofen_case_study/calliope_to_pkl.py
