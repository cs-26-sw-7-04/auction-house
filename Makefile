NS      ?= auction
CLUSTER ?= auction
IMAGE   ?= auction-house:dev
K8S_FILE ?= k8s/house.yaml
K3D_CONFIG ?= k8s/k3d-config.yaml

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

cluster-create: cluster-check ## Create the local k3s cluster (skips if it exists)
	@k3d cluster list | grep -q "^$(CLUSTER) " || k3d cluster create --config $(K3D_CONFIG)
	@kubectl config use-context k3d-$(CLUSTER)
	@kubectl get nodes

cluster-delete:       ## Delete the local cluster
	k3d cluster delete $(CLUSTER)

cluster-restart: cluster-delete cluster-create ## Recreate the cluster from scratch

image-build:           ## Build the auction-house Docker image
	docker build -t $(IMAGE) .

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

# Short aliases kept for compatibility with the previous Makefile.
khelp: help
kcheck: cluster-check
kup: cluster-create
kdown: cluster-delete
krestart: cluster-restart
kbuild: image-build
kload: image-import
kdeploy: deploy-up
kstatus:              ## Show nodes, pods, services and ingress
	kubectl get nodes
	kubectl get pods -o wide
	kubectl get svc,ingress
klogs: deploy-logs

up: deploy-up
down: deploy-down
restart: cluster-restart deploy-up
build: image-build
load: image-import
deploy: deploy-up
status: deploy-status
logs: deploy-logs
