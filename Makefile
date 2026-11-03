CLUSTER   ?= auction
IMAGE     ?= auction
TAG       ?= 1.0
SIM_IMAGE ?= bidder-simulator

.DEFAULT_GOAL := run

.PHONY: help check up down restart build load deploy simulator-up simulator-down status logs


# Targets for auction house raw
build:
	make -C src/vcg

run: build
	uv run app


# Kubernetes targets

khelp:                ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-16s %s\n", $$1, $$2}'

kcheck:               ## Check that the required tools are installed
	@command -v docker >/dev/null  || (echo "docker is missing" && exit 1)
	@command -v k3d >/dev/null     || (echo "k3d is missing: brew install k3d" && exit 1)
	@command -v kubectl >/dev/null || (echo "kubectl is missing: brew install kubectl" && exit 1)
	@docker info >/dev/null 2>&1   || (echo "Docker is not running" && exit 1)
	@echo "All tools OK"

kup: kcheck            ## Create the local k3s cluster (skips if it exists)
	@k3d cluster list | grep -q "^$(CLUSTER) " || k3d cluster create $(CLUSTER) \
		--servers 1 --agents 1 \
		--port "8080:80@loadbalancer"
	@kubectl config use-context k3d-$(CLUSTER)
	@kubectl get nodes

kdown:                ## Delete the local cluster
	k3d cluster delete $(CLUSTER)

krestart: kdown kup     ## Recreate the cluster from scratch

kbuild:               ## Build the auction Docker image
	docker build -t $(IMAGE):$(TAG) ..

kload: kbuild          ## Import the image into the cluster
	k3d image import $(IMAGE):$(TAG) -c $(CLUSTER)

kdeploy: kload         ## Build, import and deploy the auction service
	kubectl apply -f kubernetes/auction-services.yaml -f kubernetes/ingress.yaml
	kubectl rollout restart deployment/auction 
	kubectl rollout status deployment/auction --timeout=120s

# simulator-up:        ## Start the bidder simulator
# 	docker build -t $(SIM_IMAGE):$(TAG) ./simulator
# 	k3d image import $(SIM_IMAGE):$(TAG) -c $(CLUSTER)
# 	kubectl apply -f kubernetes/bidder_simulator/

# simulator-down:      ## Stop the bidder simulator
# 	kubectl delete -f k8s/simulator/ --ignore-not-found

kstatus:              ## Show nodes, pods, services and ingress
	kubectl get nodes
	kubectl get pods -o wide
	kubectl get svc,ingress

klogs:                ## Follow the auction logs
	kubectl logs -l app=auction --tail=50 -f
