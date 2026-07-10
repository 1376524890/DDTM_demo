SHELL := /bin/bash

.PHONY: setup-zkp test-zkp test-contracts test-gateway test-v1 up down reset logs smoke

setup-zkp:
	cd ddtm_zkp && mkdir -p bin artifacts/v1 ../ddtm_evm/contracts/generated && \
		go build -o bin/v1setup ./cmd/v1setup && \
		./bin/v1setup --artifacts artifacts/v1 --contracts ../ddtm_evm/contracts/generated && \
		go build -o bin/v1prove ./cmd/v1prove

test-zkp:
	cd ddtm_zkp && go test ./v1/... ./cmd/v1setup ./cmd/v1prove ./cmd/v1prover

test-contracts: setup-zkp
	cd ddtm_evm && npm install --no-audit --no-fund && \
		DDTM_V1_REAL_ZKP=1 DDTM_V1_PROVER_BIN=../ddtm_zkp/bin/v1prove \
		DDTM_V1_ZKP_ARTIFACTS=../ddtm_zkp/artifacts/v1 npx hardhat test

test-gateway:
	cd services/gateway && npm install --no-audit --no-fund && npm test

test-v1: test-zkp test-contracts test-gateway

up:
	docker compose up --build -d

down:
	docker compose down

reset:
	docker compose down -v --remove-orphans

logs:
	docker compose logs -f --tail=200

smoke:
	bash scripts/v1_smoke.sh
