CLUSTER   ?= auction

check:               ## Check that the required tools are installed
	@command -v docker >/dev/null || (echo "docker is missing" && exit 1)
	@command -v kind >/dev/null   || (echo "kind is missing: brew install kind" && exit 1)
	@command -v kubectl >/dev/null || (echo "kubectl is missing: brew install kubectl" && exit 1)
	@docker info >/dev/null 2>&1  || (echo "Docker is not running" && exit 1)
	@echo "All tools OK"

up: check            ## Create the local cluster (skips if it exists)
	@kind get clusters | grep -qx $(CLUSTER) || kind create cluster --name $(CLUSTER) --config kind-config.yaml
	@kubectl config use-context kind-$(CLUSTER)
	@kubectl get nodes

down:                ## Delete the local cluster
	kind delete cluster --name $(CLUSTER)