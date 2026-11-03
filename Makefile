CLUSTER   ?= auction
IMAGE     ?= auction
TAG       ?= 1.0
SIM_IMAGE ?= bidder-simulator

.PHONY: help check up down restart build load deploy simulator-up simulator-down status logs

help:                ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-16s %s\n", $$1, $$2}'

check:               ## Check that the required tools are installed
	@command -v docker >/dev/null  || (echo "docker is missing" && exit 1)
	@command -v k3d >/dev/null     || (echo "k3d is missing: brew install k3d" && exit 1)
	@command -v kubectl >/dev/null || (echo "kubectl is missing: brew install kubectl" && exit 1)
	@docker info >/dev/null 2>&1   || (echo "Docker is not running" && exit 1)
	@echo "All tools OK"

up: check            ## Create the local k3s cluster (skips if it exists)
	@k3d cluster list | grep -q "^$(CLUSTER) " || k3d cluster create $(CLUSTER) \
		--servers 1 --agents 1 \
		--port "8080:80@loadbalancer"
	@kubectl config use-context k3d-$(CLUSTER)
	@kubectl get nodes

down:                ## Delete the local cluster
	k3d cluster delete $(CLUSTER)

restart: down up     ## Recreate the cluster from scratch

build:               ## Build the auction Docker image
	docker build -t $(IMAGE):$(TAG) ..

load: build          ## Import the image into the cluster
	k3d image import $(IMAGE):$(TAG) -c $(CLUSTER)

deploy: load         ## Build, import and deploy the auction service
	kubectl apply -f kubernetes/auction-services.yaml -f kubernetes/ingress.yaml
	kubectl rollout restart deployment/auction 
	kubectl rollout status deployment/auction --timeout=120s

# simulator-up:        ## Start the bidder simulator
# 	docker build -t $(SIM_IMAGE):$(TAG) ./simulator
# 	k3d image import $(SIM_IMAGE):$(TAG) -c $(CLUSTER)
# 	kubectl apply -f kubernetes/bidder_simulator/

# simulator-down:      ## Stop the bidder simulator
# 	kubectl delete -f k8s/simulator/ --ignore-not-found

status:              ## Show nodes, pods, services and ingress
	kubectl get nodes
	kubectl get pods -o wide
	kubectl get svc,ingress

logs:                ## Follow the auction logs
	kubectl logs -l app=auction --tail=50 -f