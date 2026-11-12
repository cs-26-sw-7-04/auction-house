# Auctionhouse using VCG

```
cp .env.example .env
```


## run

```
uv sync
or
uv sync --extra k8s

uv run auction-house            # http://localhost:7777/docs
uv run pytest
```

`AH_AUTO_RUN=true` opens and clears auctions on a timer; otherwise the operator
does it with `POST /operator/auctions` and `POST /operator/auctions/{id}/clear`.


## Project alyout

```
domain.py        data models and errors; knows nothing else
ports.py         the interfaces (Protocols) everything plugs into
plugins.py       name -> component registries, with entry-point discovery
components/      built-in implementations of the ports
house.py         the auction flow, written against the ports only
config.py        settings; chooses components by name
bootstrap.py     settings -> wired AuctionHouse
api/             FastAPI: app factory, auth dependencies, routers
```


## Build and check auctionhouse container

```bash
# Be in docker group
sudo usermod -aG docker "$USER"
newgrp docker
```

```bash
docker build -t auction-house:dev .
docker run --rm auction-house:dev python -c "import auction_house, kubernetes; print(auction_house.__file__)"
docker run --rm -p 7777:7777 auction-house:dev
```

## k3d

### Create cluster with 3 bidders agents + control plane

```bash
k3d cluster create auction \
    --servers 1 --agents 3 \
    --k3s-node-label "auction/bidder=alice@agent:0" \
    --k3s-node-label "auction/bidder=bob@agent:1" \
    --k3s-node-label "auction/bidder=carol@agent:2" \
    -p "7777:30777@server:0" \
    --k3s-arg "--disable=traefik@server:0"

kubectl get nodes -L auction/bidder
```

### Import images (Auction house + whatever task)

```bash
k3d image import auction-house:dev -c auction
k3d image import busybox:latest -c auction   # or whatever image the demo tasks use
```

### Deploy the house

```bash
kubectl apply -f k8s/house.yaml
kubectl -n auction rollout status deploy/auction-house
kubectl -n auction logs deploy/auction-house
curl localhost:7777/health
```

### Check the house before testing Kubernetes

First time:
```bash
kubectl -n auction set env deploy/auction-house AH_DEPLOYER__NAME=log AH_DEPLOYER__OPTIONS-
```

Consequtivly:
```bash
kubectl -n auction set env deploy/auction-house \
    AH_DEPLOYER__NAME=kubernetes \
    AH_DEPLOYER__OPTIONS='{"namespace": "auction", "pin_to_node": true}'
```

### Watch jobs

```bash
kubectl -n auction get jobs,pods -o wide -w
```

### Apply and restart auction house

```bash
kubectl apply -f k8s/house.yaml
kubectl -n auction rollout restart deploy/auction-house
kubectl -n auction logs deploy/auction-house -f
```


### remove auction deployment

```bash
# Remove the auction house deployment
kubectl delete -f k8s/house.yaml --ignore-not-found
```

```bash
# Remove the entire k3d cluster
k3d cluster delete auction
```