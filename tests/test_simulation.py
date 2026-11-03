import datetime

import pytest

from simulation.energy import FixedTariff, Microgrid, MicrogridTariff, NodeProfile
from simulation.profiles import NODES
from simulation.run import simulate


def test_every_bidder_is_individually_rational_under_vcg():
    result = simulate(rounds=20, engine="vcg", seed=3)
    assert all(b["profit"] >= 0 for b in result["bidders"].values())
    assert sum(result["tasks"].values()) > 0
    assert sum(b["won"] for b in result["bidders"].values()) == result["awarded"]


def test_cheaper_energy_wins_more_and_busy_nodes_bid_less():
    bidders = simulate(rounds=20, seed=3)["bidders"]
    assert bidders["nano-3"]["won"] > bidders["nano-1"]["won"]  # mostly solar vs dear grid
    assert bidders["nano-3"]["bids"] < 20                        # busy rounds are skipped


def test_the_simulation_is_deterministic():
    assert simulate(rounds=10, seed=5) == simulate(rounds=10, seed=5)


def test_microgrid_prices_follow_the_sun():
    grid = Microgrid.synthetic()
    node = NODES[0]
    noon, night = (datetime.datetime(2026, 6, 21, h) for h in (12, 2))
    assert MicrogridTariff(node, grid).task_cost(500, noon) < MicrogridTariff(node, grid).task_cost(500, night)
    assert FixedTariff(node).task_cost(500, noon) == FixedTariff(node).task_cost(500, night)


def test_microgrid_csv_is_averaged_per_hour(tmp_path):
    rows = ["timestamp,price_eur_kwh,renewable_share"]
    for hour in range(24):
        for day, price in ((1, 0.10), (2, 0.20)):
            rows.append(f"2026-06-{day:02d}T{hour:02d}:00:00,{price},0.5")
    csv = tmp_path / "grid.csv"
    csv.write_text("\n".join(rows))
    assert Microgrid.from_csv(csv).at(datetime.datetime(2026, 1, 1, 7)) == pytest.approx((0.15, 0.5))
    with pytest.raises(ValueError):
        Microgrid({0: (0.1, 0.0)})
