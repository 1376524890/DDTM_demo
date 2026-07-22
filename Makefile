SHELL := /bin/bash
ROOT := $(shell pwd)

.PHONY: all canonicalizer evaluator zk-test zk-setup optimizer contracts-test format clean lint

all: canonicalizer evaluator

canonicalizer:
	cd canonicalizer-go && go build -o $(ROOT)/bin/ddtm-canonicalize ./cmd/ddtm-canonicalize

evaluator:
	cd tee-evaluator-rust && cargo build --release
	cp tee-evaluator-rust/target/release/ddtm-tee-evaluator $(ROOT)/bin/

zk-test:
	cd zk && go test -v ./...

zk-setup:
	mkdir -p artifacts/zk
	cd zk && go run ./cmd/setup --circuit utility --out $(ROOT)/artifacts/zk/utility --unsafe-development-setup
	cd zk && go run ./cmd/setup --circuit audit --out $(ROOT)/artifacts/zk/audit --unsafe-development-setup

optimizer:
	python services/policy_optimizer/optimizer.py --config experiments/configs/policy-default.json --output experiments/policy-default-result.json

contracts-build:
	cd contracts && forge build

contracts-test:
	cd contracts && forge test -vv

format:
	cd canonicalizer-go && gofmt -w .
	cd zk && gofmt -w .
	cd tee-evaluator-rust && cargo fmt 2>/dev/null || true
	python -m black services ml experiments 2>/dev/null || true

lint:
	cd canonicalizer-go && go vet ./...
	cd zk && go vet ./...
	cd tee-evaluator-rust && cargo clippy -- -D warnings 2>/dev/null || true

clean:
	rm -rf bin/
	cd canonicalizer-go && go clean
	cd tee-evaluator-rust && cargo clean
	cd contracts && forge clean

docker-up:
	docker compose up -d postgres minio anvil 2>/dev/null || \
	docker-compose up -d postgres minio anvil 2>/dev/null || \
	echo "docker-compose not available, skipping"

docker-down:
	docker compose down 2>/dev/null || \
	docker-compose down 2>/dev/null || \
	echo "docker-compose not available, skipping"

docker-status:
	docker compose ps 2>/dev/null || \
	docker-compose ps 2>/dev/null || \
	docker ps

# ------------------------------------------------------------------
# Docker-based experiments (isolated, reproducible)
# ------------------------------------------------------------------
DOCKER_IMG := ddtm-experiments:latest
DOCKER_RUN := docker run --rm \
	-v "$(ROOT):/workspace" \
	-v "$(shell go env GOMODCACHE 2>/dev/null || echo $(HOME)/go/pkg/mod):/root/go/pkg/mod" \
	-e GOMODCACHE=/root/go/pkg/mod \
	-e GOPATH=/root/go \
	-e GOTOOLCHAIN=local \
	-w /workspace \
	$(DOCKER_IMG) \
	bash -c "git config --global --add safe.directory /workspace 2>/dev/null; exec bash \"\$@\"" --

docker-build:
	docker build -t $(DOCKER_IMG) -f experiments/Dockerfile .

docker-experiment:
	$(DOCKER_RUN) bash experiments/e2e_test.sh

docker-experiment-report:
	$(DOCKER_RUN) python3 experiment-report.py

docker-shell:
	$(DOCKER_RUN) bash

docker-zk-test:
	$(DOCKER_RUN) bash -c "cd zk && go test -v ./..."

docker-contracts-test:
	$(DOCKER_RUN) bash -c "cd contracts && forge test -vv"

docker-clean-experiments:
	rm -rf experiments/results/*.json experiments/vectors/*.bin data/raw/synthetic.npz

data-prep:
	mkdir -p data/prepared data/raw artifacts/model artifacts/reports
	python ml/prepare_tabular.py \
		--input data/raw/covertype.parquet \
		--label target \
		--output data/prepared/covertype \
		--seller-rows 100000 \
		--validation-rows 20000 \
		--seed 20260721

model-train:
	CUDA_VISIBLE_DEVICES=0 python ml/train_buyer_model.py \
		--base data/prepared/covertype/base.npz \
		--validation data/prepared/covertype/validation.npz \
		--output artifacts/model/model-q16.json \
		--epochs 30 \
		--seed 20260721

probe-train:
	python ml/train_audit_probe.py \
		--input data/prepared/covertype/validation.npz \
		--output artifacts/model/audit-probe.json \
		--seed 20260721

canonicalize:
	mkdir -p artifacts/data
	bin/ddtm-canonicalize \
		--input data/prepared/covertype/seller-canonical-input.csv \
		--schema data/prepared/covertype/preprocessing-policy.json \
		--output artifacts/data/seller.canonical.bin \
		--manifest artifacts/data/seller.manifest.json \
		--dataset-version 1
	bin/ddtm-canonicalize \
		--input data/prepared/covertype/validation-canonical-input.csv \
		--schema data/prepared/covertype/preprocessing-policy.json \
		--output artifacts/data/validation.canonical.bin \
		--manifest artifacts/data/validation.manifest.json \
		--dataset-version 1

evaluate:
	mkdir -p artifacts/reports
	tee-evaluator-rust/target/release/ddtm-tee-evaluator evaluate \
		--seller artifacts/data/seller.canonical.bin \
		--seller-rows 100000 \
		--validation artifacts/data/validation.canonical.bin \
		--validation-rows 20000 \
		--model artifacts/model/model-q16.json \
		--policy artifacts/policy/utility-policy.json \
		--seed-hex $(shell printf '00%.0s' {1..64}) \
		--output artifacts/reports/utility-report.json

deploy:
	bash deployment/dev/deploy.sh
