# Running experiments on the auction house

Two parts:

- **Part A** is done once: Harbor, cluster, images.
- **Part B** is done per experiment: one folder describes it, one command starts it, one collects results, one resets it.

An experiment is four small files: house settings, API keys, bidders, and image versions. Switching experiments means pointing at a different folder.

```
[Harbor]  images: auction-house, bidder, busybox
    |
[k3d cluster "auction"]
    |-- house (1 pod)          <- experiments/<name>/house.env, keys.json
    |-- bidders (1 pod each)   <- experiments/<name>/bidders.yaml
    '-- task Jobs (created by the house, on the winner's node)
```

Tools needed: `docker`, `k3d`, `kubectl`, `helm`, `jq`, `envsubst` (package `gettext`), `make`, `uv`.

---

# Part A: one-time setup

## A0. Variables

Use the laptop's IP, not `localhost`. The cluster nodes are Docker containers, and inside them `localhost` means the node itself.

```bash
hostname -I                              # pick the LAN IP, e.g. 192.168.1.50
export REGISTRY=192.168.1.50:8080
export PROJECT=auction
```

The IP must stay the same. If the laptop changes network, image names and the cluster config break. Use a fixed address, a phone hotspot with a stable IP, or a Tailscale IP.

## A1. Install Harbor

Harbor runs as a set of Docker containers on the laptop. This setup uses plain HTTP, which is fine locally.

Download the offline installer from <https://github.com/goharbor/harbor/releases>, then:

```bash
tar xzf harbor-offline-installer-*.tgz
cd harbor
cp harbor.yml.tmpl harbor.yml
```

Edit `harbor.yml`:

```yaml
hostname: 192.168.1.50
http:
    port: 8080
# comment out the whole https: block
harbor_admin_password: choose-a-password
```

Install:

```bash
sudo ./install.sh
```

Open `http://192.168.1.50:8080` and log in as `admin`. Then in the UI:

1. Create a project named `auction`, access level private.
2. In the project, create two robot accounts:
    - `push`: push and pull. Used on your machine.
    - `pull`: pull only. Used by the cluster.
3. Save both tokens. They are shown once. Robot names look like `robot$auction+pull`, so single-quote them in the shell.
4. In the project settings, enable tag immutability, so a tag can never be overwritten.

Harbor comes back after a reboot on its own (its containers restart with Docker). To stop or start it by hand: `cd harbor && sudo docker compose down` and `sudo docker compose up -d`. Its data stays in `/data`.

## A2. Let Docker push to an HTTP registry

Edit `/etc/docker/daemon.json`:

```json
{
    "insecure-registries": ["192.168.1.50:8080"]
}
```

```bash
sudo systemctl restart docker
cd harbor && sudo docker compose up -d     # if Harbor did not come back
docker login $REGISTRY -u 'robot$auction+push'
```

If the file already has settings, add the key to the existing object.

## A3. Create the cluster

Create `registries.yaml`. It tells every node how to reach Harbor and gives it the pull credentials, so Kubernetes needs no pull secrets. It holds a token, so add it to `.gitignore`.

```yaml
mirrors:
    "192.168.1.50:8080":
        endpoint:
            - "http://192.168.1.50:8080"
configs:
    "192.168.1.50:8080":
        auth:
            username: 'robot$auction+pull'
            password: '<pull token>'
```

```bash
k3d cluster create auction \
    --servers 1 --agents 3 \
    --registry-config registries.yaml \
    --k3s-node-label "auction/bidder=alice@agent:0" \
    --k3s-node-label "auction/bidder=bob@agent:1" \
    --k3s-node-label "auction/bidder=carol@agent:2" \
    -p "7777:30777@server:0" \
    --k3s-arg "--disable=traefik@server:0"

kubectl get nodes -L auction/bidder
kubectl create namespace auction
```

Each agent carries one bidder name. With `pin_to_node` on, a bidder can only win work if a node has its label. For more bidders, add agents and one label flag per agent, or set `pin_to_node` to false in `house.env` (then Jobs run anywhere, and bidder names are only identities).

If pulls time out later, the laptop's firewall may block Docker containers from reaching port 8080.

## A4. Publish images

House repo:

```bash
TAG=$(git rev-parse --short HEAD)          # commit first
docker build -t $REGISTRY/$PROJECT/auction-house:$TAG .
docker push $REGISTRY/$PROJECT/auction-house:$TAG
echo $TAG
```

Bidder repo, with this `Makefile`. `.RECIPEPREFIX` means recipe lines start with `>` instead of a tab.

```make
.RECIPEPREFIX = >
ifndef REGISTRY
$(error export REGISTRY first)
endif
PROJECT ?= auction
TAG     ?= $(shell git rev-parse --short HEAD)
IMAGE   := $(REGISTRY)/$(PROJECT)/bidder:$(TAG)

.PHONY: push
push:
> docker build -t $(IMAGE) .
> docker push $(IMAGE)
> @echo pushed $(IMAGE)
```

```bash
make push
```

Task image (what the demo tasks run):

```bash
docker pull busybox:1.36
docker tag busybox:1.36 $REGISTRY/$PROJECT/busybox:1.36
docker push $REGISTRY/$PROJECT/busybox:1.36
```

Check that the cluster can pull from Harbor:

```bash
kubectl -n auction run pulltest --image=$REGISTRY/$PROJECT/busybox:1.36 --restart=Never --command -- true
kubectl -n auction get pod pulltest        # Completed, not ImagePullBackOff
kubectl -n auction delete pod pulltest
```

Tags are immutable, so every code change needs a new commit and a new tag. That is intentional: an experiment always says exactly what code it ran.

---

# Part B: experiments

## B1. Layout

Put this in the bidder repo, next to `chart/`.

```
experiments/
    Makefile
    house.yaml              # shared: how the house is deployed
    vcg/
        house.env
        keys.json
        bidders.yaml
        versions.mk
    pay-as-bid/
        ...
    results/
```

## B2. Shared `experiments/house.yaml`

The ConfigMap and the keys Secret are not here. Each experiment supplies them.

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
    name: auction-house
    namespace: auction
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
    name: auction-house-jobs
    namespace: auction
rules:
    - apiGroups: ["batch"]
      resources: ["jobs"]
      verbs: ["create", "get", "list", "delete"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
    name: auction-house-jobs
    namespace: auction
subjects:
    - kind: ServiceAccount
      name: auction-house
      namespace: auction
roleRef:
    apiGroup: rbac.authorization.k8s.io
    kind: Role
    name: auction-house-jobs
---
apiVersion: apps/v1
kind: Deployment
metadata:
    name: auction-house
    namespace: auction
spec:
    # State is in memory: exactly one replica, never two pods at once.
    replicas: 1
    strategy:
        type: Recreate
    selector:
        matchLabels:
            app: auction-house
    template:
        metadata:
            labels:
                app: auction-house
        spec:
            serviceAccountName: auction-house
            containers:
                - name: house
                  image: ${HOUSE_IMAGE}
                  imagePullPolicy: IfNotPresent
                  ports:
                      - containerPort: 7777
                  envFrom:
                      - configMapRef:
                            name: auction-house-config
                      - secretRef:
                            name: auction-house-keys
                  readinessProbe:
                      httpGet:
                          path: /health
                          port: 7777
                      periodSeconds: 5
                  livenessProbe:
                      httpGet:
                          path: /health
                          port: 7777
                      initialDelaySeconds: 10
                      periodSeconds: 10
                  resources:
                      requests:
                          cpu: 100m
                          memory: 128Mi
                      limits:
                          memory: 512Mi
---
apiVersion: v1
kind: Service
metadata:
    name: auction-house
    namespace: auction
spec:
    type: NodePort
    selector:
        app: auction-house
    ports:
        - port: 7777
          targetPort: 7777
          nodePort: 30777
```

## B3. The files of one experiment

`experiments/vcg/house.env`. Plain `KEY=value` lines, no quotes around values. Durations are ISO 8601 (`PT30S`), never plain numbers.

```
AH_AUTO_RUN=true
AH_TICK=PT1S
AH_BIDDING_WINDOW=PT30S
AH_MAX_ROUNDS=3
AH_GROUPER__NAME=batch
AH_GROUPER__OPTIONS={"size": 6}
AH_SOLVER__NAME=brute-force
AH_ENGINE__NAME=vcg
AH_DEPLOYER__NAME=kubernetes
AH_DEPLOYER__OPTIONS={"namespace": "auction", "pin_to_node": true}
```

`size` is 6 because the simulated bidders only bundle the first 6 tasks of an auction. A larger batch leaves tasks nobody can bid on.

`experiments/vcg/keys.json`. Every bidder listed in `bidders.yaml` needs an entry with the same name and key.

```json
{
    "op-key":    {"role": "operator",  "id": "ops"},
    "sub-key":   {"role": "submitter", "id": "submitter1"},
    "alice-key": {"role": "bidder",    "id": "alice"},
    "bob-key":   {"role": "bidder",    "id": "bob"},
    "carol-key": {"role": "bidder",    "id": "carol"}
}
```

`experiments/vcg/bidders.yaml`. The image is not listed here, it comes from `versions.mk`.

```yaml
defaults:
    houseUrl: http://auction-house.auction.svc.cluster.local:7777
    resources:
        requests: {cpu: 20m, memory: 64Mi}
        limits: {memory: 256Mi}

bidders:
    - name: alice
      apiKey: alice-key
      args: [simple, --generation=100, --consumption=10, --grid-price=1.0]
    - name: bob
      apiKey: bob-key
      args: [simple, --generation=0, --consumption=10, --grid-price=1.0]
    - name: carol
      apiKey: carol-key
      args: [data, --dataset=data/processed/aau_power_1min.parquet, --speed=60]
```

`experiments/vcg/versions.mk`, the tags printed by A4:

```make
HOUSE_TAG  := a1b2c3d
BIDDER_TAG := e4f5g6h
```

## B4. `experiments/Makefile`

```make
.RECIPEPREFIX = >
ifndef REGISTRY
$(error export REGISTRY first)
endif

NS      ?= auction
PROJECT ?= auction
URL     ?= http://localhost:7777
OP_KEY  ?= op-key
SUB_KEY ?= sub-key

-include $(EXP)/versions.mk
HOUSE_IMAGE  := $(REGISTRY)/$(PROJECT)/auction-house:$(HOUSE_TAG)
BIDDER_IMAGE := $(REGISTRY)/$(PROJECT)/bidder:$(BIDDER_TAG)

.PHONY: check-exp up reset collect progress down

check-exp:
> @test -n "$(EXP)" || (echo "usage: make <target> EXP=<experiment>"; exit 1)
> @test -d "$(EXP)" || (echo "no such experiment: $(EXP)"; exit 1)

up: check-exp
> kubectl -n $(NS) create configmap auction-house-config --from-env-file=$(EXP)/house.env --dry-run=client -o yaml | kubectl apply -f -
> kubectl -n $(NS) create secret generic auction-house-keys --from-file=AH_API_KEYS=$(EXP)/keys.json --dry-run=client -o yaml | kubectl apply -f -
> HOUSE_IMAGE=$(HOUSE_IMAGE) envsubst '$$HOUSE_IMAGE' < house.yaml | kubectl apply -f -
> kubectl -n $(NS) rollout restart deploy/auction-house
> kubectl -n $(NS) rollout status deploy/auction-house
> helm upgrade --install bidders ../chart -n $(NS) -f $(EXP)/bidders.yaml --set defaults.image=$(BIDDER_IMAGE)
> kubectl -n $(NS) rollout restart deploy -l app=bidder
> kubectl -n $(NS) rollout status deploy -l app=bidder
> @echo "experiment $(EXP) is up: $(HOUSE_IMAGE) / $(BIDDER_IMAGE)"

reset:
> kubectl -n $(NS) delete jobs --all
> kubectl -n $(NS) rollout restart deploy/auction-house
> kubectl -n $(NS) rollout status deploy/auction-house
> kubectl -n $(NS) rollout restart deploy -l app=bidder
> kubectl -n $(NS) rollout status deploy -l app=bidder

progress:
> curl -s $(URL)/tasks -H "X-API-Key: $(SUB_KEY)" | jq 'group_by(.status) | map({(.[0].status): length}) | add'

collect: check-exp
> mkdir -p results/$(EXP)/auctions
> curl -sf $(URL)/auctions -H "X-API-Key: $(OP_KEY)" | jq -r '.[].auction_id' | while read id; do curl -sf $(URL)/operator/auctions/$$id -H "X-API-Key: $(OP_KEY)" > results/$(EXP)/auctions/$$id.json; done
> curl -sf $(URL)/tasks -H "X-API-Key: $(SUB_KEY)" > results/$(EXP)/tasks.json
> kubectl -n $(NS) logs deploy/auction-house > results/$(EXP)/house.log
> for d in $$(kubectl -n $(NS) get deploy -l app=bidder -o name); do kubectl -n $(NS) logs $$d > results/$(EXP)/$$(basename $$d).log; done
> cp -r $(EXP) results/$(EXP)/config
> @echo "saved to results/$(EXP)"

down:
> -helm uninstall bidders -n $(NS)
> -kubectl -n $(NS) delete jobs --all
> -kubectl -n $(NS) delete deploy/auction-house
```

The `X-API-Key` header is a guess. If you get 401 or 403, check how `api/deps.py` reads the key and change the three `curl` lines.

## B5. Running one experiment

```bash
cd experiments
make up EXP=vcg                  # house + bidders, with this experiment's config
```

Start your task submission script now (Part C), or the demo loop below. Bidders must be running first, since an auction only collects bids while it is open.

```bash
make progress                    # repeat until nothing is pending/in_auction/executing
make collect EXP=vcg             # results/vcg/: auctions, tasks, logs, a copy of the config
```

Collect before resetting. The house keeps everything in memory, so a restart erases it.

Run the same experiment again from a clean state:

```bash
make reset
```

`reset` deletes all Jobs and restarts the house and every bidder. Restarting the bidders matters for `data` bidders, because their replay clock starts when the pod starts.

## B6. A different configuration

Copy the folder and change what you want to test:

```bash
cp -r vcg pay-as-bid
# edit pay-as-bid/house.env: AH_ENGINE__NAME=pay-as-bid
make up EXP=pay-as-bid
```

Everything that can differ between experiments:

| What                    | Where                                        |
|-------------------------|----------------------------------------------|
| Payment rule            | `house.env`: `AH_ENGINE__NAME` (`vcg`, `pay-as-bid`) |
| Solver                  | `house.env`: `AH_SOLVER__NAME`               |
| Bidding window          | `house.env`: `AH_BIDDING_WINDOW`             |
| Retries per task        | `house.env`: `AH_MAX_ROUNDS`                 |
| Tasks per auction       | `house.env`: `AH_GROUPER__OPTIONS` (`size`)  |
| Job placement           | `house.env`: `pin_to_node` in `AH_DEPLOYER__OPTIONS` |
| Number of bidders       | `bidders.yaml` and `keys.json`               |
| Bidder cost and margin  | `bidders.yaml` args: `--generation`, `--consumption`, `--grid-price`, `--compute`, `--margin` |
| Bidder type             | `bidders.yaml` args: `simple` or `data` (`--dataset`, `--start`, `--speed`) |
| House or bidder code    | `versions.mk` tags                           |
| Workload                | your submission script's parameters (store them in the experiment folder) |

`--margin` is the only strategy knob. Bidders otherwise ask their true cost. Raising the margin for one bidder raises its payment under pay-as-bid and only costs it wins under VCG, which makes a margin sweep a direct test of the mechanism.

Switching experiment on a running cluster is `make up EXP=<other>`. Bidders removed from the new `bidders.yaml` are deleted by Helm, and the house restarts with the new config.

## B7. Teardown

| Goal                                  | Command                                              |
|---------------------------------------|------------------------------------------------------|
| Empty state, same experiment          | `make reset`                                         |
| Stop the experiment, keep the cluster | `make down`                                          |
| Remove the cluster                    | `k3d cluster delete auction`                         |
| Stop Harbor                           | `cd harbor && sudo docker compose down`              |
| Remove Harbor and its images          | stop it, then `sudo rm -rf /data` and delete the folder |

After deleting the cluster, redo A3 and `kubectl create namespace auction`. Harbor and its images stay, so A1, A2 and A4 are not repeated.

---

# Part C: submitting many tasks

Your script talks to the house over HTTP on `localhost:7777`, with the submitter key.

`POST /tasks`, one request per task:

```json
{
    "image": "192.168.1.50:8080/auction/busybox:1.36",
    "deadline": "2026-11-10T18:00:00Z",
    "max_budget": 10,
    "resources": {"cpu_millis": 500, "memory_mb": 128, "gpu": false},
    "verification": "none"
}
```

A minimal version:

```python
import datetime
import httpx

client = httpx.Client(base_url="http://localhost:7777", headers={"X-API-Key": "sub-key"}, timeout=10)
deadline = (datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=2)).isoformat()

for i in range(100):
    response = client.post("/tasks", json={
        "image": "192.168.1.50:8080/auction/busybox:1.36",
        "deadline": deadline,
        "max_budget": 10,
        "resources": {"cpu_millis": 500, "memory_mb": 128},
        "verification": "none",
    })
    response.raise_for_status()
```

Rules and limits:

- **Deadline** must be in the future. The Job is also killed at the deadline, so give it hours, not seconds.
- **Image** must be in Harbor, under a project the pull robot can read.
- **`verification` must be `none`** with the current bidders, because they report no result hash.
- **Grouping.** The house takes pending tasks, sorted by submission time, and splits them into auctions of `size` tasks. Auctions open on the next tick and all stay open for the bidding window.
- **Clearing is sequential.** Each auction costs one solve plus one solve per winner. With many auctions, total clearing time is the sum. Tasks nobody wins return to pending until `AH_MAX_ROUNDS`, then become `unallocated`.
- **Brute force grows exponentially with the number of bidders.** It is fine for a few bidders with up to 63 bundles each. Test the largest setup you plan on with one auction before submitting hundreds. For more bidders you need the C or an ILP solver.
- **Node capacity.** Each task becomes a Pod. If the winner's node lacks CPU or memory, the Pod stays `Pending`, the task stays `executing`, and `progress` never finishes. Keep `cpu_millis` small relative to the nodes, and clean up with `make reset` between runs.
- **Submission rate** is not limited by the house, but all tasks in the same tick end up in the same set of auctions. To spread load over time, sleep between submissions.

---

# Troubleshooting

| Symptom                                     | Cause and fix                                              |
|---------------------------------------------|------------------------------------------------------------|
| `docker push`: `http: server gave HTTP response to HTTPS client` | A2 not done, or Docker not restarted             |
| `ImagePullBackOff`, `unauthorized`          | wrong token in `registries.yaml`, or robot lacks pull rights. Recreate the cluster after fixing |
| `ImagePullBackOff`, `i/o timeout`           | firewall blocks Docker from reaching port 8080, or the IP changed |
| `ImagePullBackOff`, `manifest unknown`      | the tag was never pushed                                   |
| `push` fails: tag already exists            | immutability is working. Commit and use a new tag          |
| House `CrashLoopBackOff`                    | `kubectl -n auction logs deploy/auction-house`             |
| `Input should be a valid timedelta`         | use `PT30S` in `house.env`                                 |
| `unknown solver`                            | name not registered in the house image                     |
| 403 when deploying a Job                    | Role missing. `kubectl auth can-i create jobs -n auction --as=system:serviceaccount:auction:auction-house` |
| Bidder log: `Request failed`                | house URL, key or auth header wrong                        |
| Bidders bid, nobody wins                    | asks above the task budgets, or bundles not matching the house fields |
| Task stays `executing`                      | Pod `Pending`: no node with the label, or no capacity      |
| `progress` prints `null`                    | no tasks submitted, or wrong submitter key                 |
| `make`: `missing separator`                 | a recipe line starts with spaces instead of `>`            |