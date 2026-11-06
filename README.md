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