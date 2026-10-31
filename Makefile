.PHONY: install lint-jev-questions gate4-closed data-validate verify-backtest engine-parity jev-gate test ci-grep-typesafe

install:
	pip install -e ".[dev]"

lint-jev-questions:
	lint-jev-questions ID=$(ID)

gate4-closed:
	python -c "from week_trader.gate4 import assert_gate4_closed; assert_gate4_closed(); print('gate4 closed')"

data-validate:
	data-validate $(MANIFEST)

verify-backtest:
	verify-backtest ID=$(ID)

engine-parity:
	engine-parity ID=$(ID) $(if $(WRITE_RUN),--write-run,)

jev-gate:
	jev-gate ID=$(ID) GATE=$(GATE)

test:
	pytest -q

ci-grep-typesafe:
	! rg -n "api\\.typesafe\\.ai|call_system_one" --glob '!week_trader/typesafe_client.py' --glob '!week_trader/jev_gate.py' week_trader scripts || (echo 'TypeSafe calls outside allowed modules' && exit 1)

ci: install gate4-closed lint-jev-questions data-validate ci-grep-typesafe test
