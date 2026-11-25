CLUSTER   ?= auction
IMAGE     ?= auction
TAG       ?= 1.0
SIM_IMAGE ?= bidder-simulator
K3S_IMAGE ?= rancher/k3s:v1.31.5-k3s1

.DEFAULT_GOAL := run

.PHONY: help check up down restart build load deploy status logs \
	cluster-check cluster-create cluster-delete cluster-restart image-build image-import \
	deploy-up deploy-down deploy-status deploy-logs


# Targets for auction house raw
build:
	make -C src/vcg

run: build
	uv run app


# Kubernetes targets

help:                 ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-16s %s\n", $$1, $$2}'

cluster-check:        ## Check that the required cluster tools are installed
	@command -v docker >/dev/null  || (echo "docker is missing" && exit 1)
	@command -v k3d >/dev/null     || (echo "k3d is missing" && exit 1)
	@command -v kubectl >/dev/null || (echo "kubectl is missing" && exit 1)
	@docker info >/dev/null 2>&1   || (echo "Docker is not running" && exit 1)
	@echo "All tools OK"

kup: kcheck            ## Create the local k3s cluster (skips if it exists)
	@k3d cluster list | grep -q "^$(CLUSTER) " || k3d cluster create $(CLUSTER) \
		--image $(K3S_IMAGE) \
		--servers 1 --agents 1 \
		--port "8080:80@loadbalancer"
	@kubectl config use-context k3d-$(CLUSTER)
	@kubectl get nodes

cluster-delete:       ## Delete the local cluster
	k3d cluster delete $(CLUSTER)

cluster-restart: cluster-delete cluster-create ## Recreate the cluster from scratch

kbuild:               ## Build the auction Docker image
	docker build -t $(IMAGE):$(TAG) .

image-import: image-build ## Import the image into the cluster
	k3d image import $(IMAGE) -c $(CLUSTER)

deploy-up: image-import ## Build, import and deploy the auction service
	kubectl apply -f $(K8S_FILE)
	kubectl -n $(NS) rollout status deployment/auction-house --timeout=120s

deploy-down:          ## Remove the auction service
	kubectl delete -f $(K8S_FILE) --ignore-not-found

deploy-status:        ## Show auction-house pods and service
	kubectl -n $(NS) get pods,svc -l app=auction-house -o wide

deploy-logs:          ## Follow the auction-house logs
	kubectl -n $(NS) logs deploy/auction-house --tail=50 -f
