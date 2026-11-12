# Auction house and bidders: full setup

Two repos, one cluster, one registry.

| Repo           | Contains                                          | Produces                  |
|----------------|---------------------------------------------------|---------------------------|
| `auction-house`| the house, `Dockerfile`, `k8s/house.yaml`         | image `auction-house`     |
| `bidder-sim`   | `main.py`, `simulator.py`, `chart/`, `bidders.yaml`, `Makefile` | image `bidder` |

Everything is set up in this order. Do not skip ahead.

1. Harbor
2. Cluster
3. Namespace and pull secret
4. House
5. Bidders
6. Run a demo
7. Change things later
8. Tear down

Commands are marked **[house]** or **[bidder]** for the repo to run them in.

---

## 0. Decide these once

Replace the values and export them in every terminal you use. Nothing else in this guide needs editing.

```bash
export REGISTRY=harbor.example.com   # your Harbor hostname
export PROJECT=auction               # Harbor project name
export TAG=1.0                       # bump on every release
```

Names that must match everywhere:

| Thing                     | Where it appears                                                      |
|---------------------------|------------------------------------------------------------------------|
| bidder name (`alice`)     | `bidders.yaml` `name`, house `AH_API_KEYS` id, node label `auction/bidder=alice` |
| bidder key (`alice-key`)  | `bidders.yaml` `apiKey`, house `AH_API_KEYS` key                       |
| cluster name (`auction`)  | `k3d cluster create`, `k3d` commands                                   |
| namespace (`auction`)     | everything in Kubernetes                                               |

---

## 1. Harbor

In the Harbor web UI:

1. Create a project named `auction`.
2. Create two robot accounts in that project:
    - `push`: push and pull. Used on your machine.
    - `pull`: pull only. Used by the cluster.
3. Save both tokens. Harbor shows them once. Robot names look like `robot$auction+pull`; always single-quote them in the shell.
4. In the project settings, turn on tag immutability so a tag cannot be overwritten.

Log in from your machine:

```bash
docker login $REGISTRY -u 'robot$auction+push'
```

Check that the cluster's nodes can reach Harbor. This is the most common failure and is explained in section 2.

---

## 2. Cluster

One server and three agents. Each agent carries a bidder label. The house runs Jobs on the agent with the winner's label.

If Harbor has a certificate from a public CA and a name that resolves from inside Docker:

```bash
k3d cluster create auction \
    --servers 1 --agents 3 \
    --k3s-node-label "auction/bidder=alice@agent:0" \
    --k3s-node-label "auction/bidder=bob@agent:1" \
    --k3s-node-label "auction/bidder=carol@agent:2" \
    -p "7777:30777@server:0" \
    --k3s-arg "--disable=traefik@server:0"
```

If Harbor uses a self-signed certificate, create `registries.yaml`:

```yaml
configs:
    "harbor.example.com":
        tls:
            ca_file: /etc/ssl/harbor-ca.crt
```

and add these flags to the command above:

```bash
    --registry-config registries.yaml \
    --volume "$PWD/harbor-ca.crt:/etc/ssl/harbor-ca.crt@all"
```

If the Harbor name only resolves on your laptop (for example an `/etc/hosts` entry), the nodes cannot see it. Add:

```bash
    --host-alias "<harbor-ip>:harbor.example.com"
```

`localhost` never works as a Harbor address, because inside a node it means the node itself.

Check:

```bash
kubectl get nodes -L auction/bidder
```

Expected: four nodes, with `alice`, `bob` and `carol` on the three agents.

---

## 3. Namespace and pull secret

Run once, before anything is deployed.

```bash
kubectl create namespace auction

kubectl -n auction create secret docker-registry harbor-pull \
    --docker-server=$REGISTRY \
    --docker-username='robot$auction+pull' \
    --docker-password='<pull token>'

kubectl -n auction patch serviceaccount default \
    -p '{"imagePullSecrets":[{"name":"harbor-pull"}]}'
```

The `default` service account is used by the bidder pods and by the task Jobs. The house has its own service account, which gets the secret in `house.yaml` below.

---

## 4. House  **[house]**

### 4.1 Files the repo must have

- `Dockerfile`: multi-stage, with `uv sync --no-dev --no-editable --extra k8s`, a non-root user and `CMD ["auction-house"]`.
- `pyproject.toml` with `auction-house = "auction_house.__main__:main"` under `[project.scripts]`, and a `k8s` extra containing `kubernetes`.
- In `src/auction_house/config.py`, the default solver set to `brute-force` (not `sorted`).
- `house.py`, `ports.py`, `domain.py`, `solvers.py`, `engines.py`, `deployers.py` and the API updated for combinatorial bids, as in the earlier changes. The pod crashes at startup otherwise.

### 4.2 `k8s/house.yaml`

Do not put the Namespace in this file. It was created in section 3.

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
    name: auction-house
    namespace: auction
imagePullSecrets:
    - name: harbor-pull
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
apiVersion: v1
kind: ConfigMap
metadata:
    name: auction-house-config
    namespace: auction
data:
    AH_AUTO_RUN: "true"
    AH_BIDDING_WINDOW: "PT30S"
    AH_TICK: "PT1S"
    AH_MAX_ROUNDS: "3"
    AH_SOLVER__NAME: "brute-force"
    AH_ENGINE__NAME: "vcg"
    AH_DEPLOYER__NAME: "kubernetes"
    AH_DEPLOYER__OPTIONS: '{"namespace": "auction", "pin_to_node": true}'
---
# Demo keys. Replace for anything that is not a local demo.
apiVersion: v1
kind: Secret
metadata:
    name: auction-house-keys
    namespace: auction
stringData:
    AH_API_KEYS: >-
        {
        "op-key":    {"role": "operator",  "id": "ops"},
        "sub-key":   {"role": "submitter", "id": "submitter1"},
        "alice-key": {"role": "bidder",    "id": "alice"},
        "bob-key":   {"role": "bidder",    "id": "bob"},
        "carol-key": {"role": "bidder",    "id": "carol"}
        }
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
                  image: harbor.example.com/auction/auction-house:1.0
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

Change the `image:` line to your `$REGISTRY`, `$PROJECT` and `$TAG` values.

### 4.3 House settings reference

All settings are `AH_*` environment variables in the ConfigMap. Durations must be ISO 8601 (`PT30S`, `PT1M`). Plain numbers are rejected.

| Setting                | Meaning                                              | Demo value |
|------------------------|------------------------------------------------------|------------|
| `AH_AUTO_RUN`          | open and clear auctions on a timer                   | `true`     |
| `AH_TICK`              | timer interval                                       | `PT1S`     |
| `AH_BIDDING_WINDOW`    | how long an auction accepts bids                     | `PT30S`    |
| `AH_MAX_ROUNDS`        | auctions a task may enter before it is given up on   | `3`        |
| `AH_SOLVER__NAME`      | `brute-force` (or `c` once bound)                    | `brute-force` |
| `AH_ENGINE__NAME`      | `vcg` or `pay-as-bid`                                | `vcg`      |
| `AH_DEPLOYER__NAME`    | `kubernetes`, or `log` to deploy nothing             | `kubernetes` |
| `AH_DEPLOYER__OPTIONS` | JSON: `namespace`, `pin_to_node`, `image_pull_policy`| see above  |
| `AH_API_KEYS`          | JSON: key to role and id                             | see above  |

Brute force handles about 8 tasks and a handful of bidders. Keep the batch size (grouper `size`, default 8) at or below that.

### 4.4 Build, push, deploy

```bash
docker build -t $REGISTRY/$PROJECT/auction-house:$TAG .
docker push $REGISTRY/$PROJECT/auction-house:$TAG

kubectl apply -f k8s/house.yaml
kubectl -n auction rollout status deploy/auction-house
```

### 4.5 Check

```bash
curl localhost:7777/health
kubectl -n auction logs deploy/auction-house
kubectl auth can-i create jobs -n auction --as=system:serviceaccount:auction:auction-house
```

Expected: `{"status":"ok"}`, no traceback in the log, and `yes`.

### 4.6 Task image for the demo

Tasks run from Harbor too. Use a tiny image:

```bash
docker pull busybox:1.36
docker tag busybox:1.36 $REGISTRY/$PROJECT/busybox:1.36
docker push $REGISTRY/$PROJECT/busybox:1.36
```

---

## 5. Bidders  **[bidder]**

### 5.1 Files the repo must have

`main.py`, `simulator.py`, `Dockerfile`, `.dockerignore`, `pyproject.toml`, `uv.lock`, `chart/Chart.yaml`, `chart/templates/bidders.yaml`, `bidders.yaml`, `Makefile`, and `data/processed/*.parquet` if you run a data bidder.

### 5.2 `bidders.yaml`

This is the only place bidders are listed.

```yaml
defaults:
    image: harbor.example.com/auction/bidder:1.0
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

To add a bidder: add an entry here, add the same name and key to `AH_API_KEYS` in the house, label a node `auction/bidder=<name>`, then redeploy both.

### 5.3 Bidder options

| Option          | Meaning                                         |
|-----------------|-------------------------------------------------|
| `--generation`  | power generated, W (`simple`)                   |
| `--consumption` | power consumed, W (`simple`)                    |
| `--dataset`     | parquet file to replay (`data`)                 |
| `--start`       | simulated start time, ISO 8601 (`data`)         |
| `--speed`       | simulated seconds per real second (`data`)      |
| `--compute`     | cost divisor, higher means cheaper              |
| `--grid-price`  | price per Wh bought from the grid               |
| `--margin`      | fraction added to the cost when asking          |

A bidder asks its true cost for every bundle. Surplus power is shared by a whole bundle, so bundles are cheaper than the sum of their tasks, which is what makes the auction combinatorial.

### 5.4 `Makefile`

Recipe lines must start with a tab.

```make
NS       ?= auction
HARBOR   ?= harbor.example.com
PROJECT  ?= auction
TAG      ?= 1.0
IMAGE    ?= $(HARBOR)/$(PROJECT)/bidder:$(TAG)

.PHONY: build push up down status logs

build:
	docker build -t $(IMAGE) .

push: build
	docker push $(IMAGE)

up: push
	helm upgrade --install bidders ./chart -n $(NS) -f bidders.yaml \
	    --set defaults.image=$(IMAGE)

down:
	helm uninstall bidders -n $(NS)

status:
	kubectl -n $(NS) get pods -l app=bidder -o wide

logs:
	kubectl -n $(NS) logs -f deploy/bidder-$(B)
```

### 5.5 Build, push, deploy

```bash
uv lock
make up HARBOR=$REGISTRY PROJECT=$PROJECT TAG=$TAG
make status
```

### 5.6 Check

```bash
make logs B=alice
```

Expected: `Bidder up, house at http://auction-house...`. No `Request failed` lines.

---

## 6. Run a demo

Bidders must be running before tasks are submitted. An auction only collects bids while it is open (30 seconds).

Submit four small tasks:

```bash
DEADLINE=$(date -u -d '+1 hour' +%Y-%m-%dT%H:%M:%SZ)

for i in 1 2 3 4; do
    curl -s -X POST localhost:7777/tasks \
        -H "X-API-Key: sub-key" -H "Content-Type: application/json" \
        -d "{\"image\": \"$REGISTRY/$PROJECT/busybox:1.36\",
             \"deadline\": \"$DEADLINE\",
             \"max_budget\": 10,
             \"resources\": {\"cpu_millis\": 500, \"memory_mb\": 128},
             \"verification\": \"none\"}"
    echo
done
```

The header name `X-API-Key` is a guess. If you get 401 or 403, check how `api/deps.py` reads the key, and for bidders set `AH_AUTH_HEADER` in the bidder Deployment.

Watch it happen, in separate terminals:

```bash
kubectl -n auction logs -f deploy/auction-house
make logs B=alice                                  # [bidder]
kubectl -n auction get jobs,pods -o wide -w
```

Then check the result:

```bash
curl -s localhost:7777/tasks -H "X-API-Key: sub-key"
```

Tasks go `pending`, `in_auction`, `executing`, `completed`. The Pods show on the agent that carries the winner's label.

---

## 7. Change things later

| Change                              | What to do                                                              |
|-------------------------------------|-------------------------------------------------------------------------|
| House setting (ConfigMap)           | edit `house.yaml`, `kubectl apply -f`, then `kubectl -n auction rollout restart deploy/auction-house` |
| House code                          | bump `TAG`, build, push, edit `image:` in `house.yaml`, `kubectl apply -f` |
| Bidder parameters or a new bidder   | edit `bidders.yaml`, `make up`                                          |
| Bidder code                         | bump `TAG`, `make up TAG=<new>`                                         |
| Add a bidder to the house           | add key to `AH_API_KEYS`, restart the house                             |

A house restart wipes all tasks, auctions and bids, because state is in memory. Jobs already started keep running.

Never reuse a tag. Nodes keep images they already have, so the old code keeps running under the same tag.

---

## 8. Tear down

```bash
make down                                  # [bidder] remove bidders
kubectl -n auction delete jobs --all       # remove leftover task Jobs
kubectl delete -f k8s/house.yaml           # [house]
k3d cluster delete auction                 # remove everything
```

---

## Troubleshooting

| Symptom                                         | Cause and fix                                                    |
|-------------------------------------------------|------------------------------------------------------------------|
| `ImagePullBackOff`, `unauthorized`              | wrong pull token or the robot lacks pull rights. Recreate `harbor-pull` |
| `ImagePullBackOff`, `x509`                      | Harbor CA not trusted by the nodes. See section 2               |
| `ImagePullBackOff`, `no such host`              | nodes cannot resolve Harbor. Use `--host-alias`                  |
| `ImagePullBackOff`, `manifest unknown`          | the tag was never pushed                                         |
| `ImagePullBackOff` only on task Jobs            | `default` service account has no `imagePullSecrets` (section 3)  |
| House `CrashLoopBackOff`                        | read `kubectl -n auction logs deploy/auction-house`; usually code not aligned or a setting is invalid |
| `Input should be a valid timedelta`             | use `PT30S`, not `30`                                            |
| 403 when deploying a Job                        | Role or RoleBinding wrong. Run the `can-i` command               |
| Bidder log shows `Request failed`               | house URL wrong, or auth header or key wrong                     |
| Bidders bid, nobody wins                        | asks are above the task budget, or bundle names do not match the house fields |
| Task stays `executing`, Pod `Pending`           | no node carries `auction/bidder=<name>`, or the node lacks CPU or memory |
| Bidder missed the auction                       | start bidders before submitting tasks                            |
| `make up` says `missing separator`              | Makefile recipe lines need tabs                                  |
| `docker build` fails on `--frozen`              | run `uv lock`                                                    |