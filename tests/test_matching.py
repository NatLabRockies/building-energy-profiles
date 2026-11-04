import math

import pandas as pd
import pytest

from building_energy_profiles import find_nearest_buildings, site_eui_kbtu_per_ft2, stack_upgrade_states
from building_energy_profiles.building_condition import KWH_TO_KBTU


def _meta():
    # EUI (kBtu/ft2) = kWh * 3.412 / sqft
    return pd.DataFrame(
        {
            "bldg_id": [1, 2, 3, 4, 5],
            "in.sqft..ft2": [10_000, 50_000, 100_000, 200_000, 0],
            "out.site_energy.total.energy_consumption..kwh": [
                10_000 * 20 / KWH_TO_KBTU,
                50_000 * 60 / KWH_TO_KBTU,
                100_000 * 80 / KWH_TO_KBTU,
                200_000 * 60 / KWH_TO_KBTU,
                1.0,
            ],
        }
    )


def test_site_eui():
    eui = site_eui_kbtu_per_ft2(_meta())
    assert eui.iloc[:4].round(6).tolist() == [20, 60, 80, 60]
    assert math.isnan(eui.iloc[4])


def test_one_shot_by_sqft_is_log_symmetric():
    # 100k target: 50k and 200k are equally far (ln 2); 100k is exact
    out = find_nearest_buildings(_meta(), sqft=100_000, k=3)
    assert out.bldg_id.tolist()[0] == 3
    assert set(out.bldg_id.tolist()[1:]) == {2, 4}
    assert out.match_distance.iloc[1] == pytest.approx(math.log(2))
    assert out.match_rank.tolist() == [1, 2, 3]


def test_sqft_and_eui_combined():
    # target 100k ft2 at 60 kBtu/ft2: bldg 3 is size-exact but EUI off by ln(80/60);
    # bldgs 2 and 4 are EUI-exact but size off by ln 2 -> bldg 3 wins
    out = find_nearest_buildings(_meta(), sqft=100_000, site_eui_kbtu_per_ft2=60, k=1)
    assert out.bldg_id.tolist() == [3]
    # weight EUI heavily -> an EUI-exact building wins
    out = find_nearest_buildings(_meta(), sqft=100_000, site_eui_kbtu_per_ft2=60, k=1, weights={"site_eui": 10})
    assert out.bldg_id.iloc[0] in (2, 4)


def test_eui_only_skips_invalid_rows():
    out = find_nearest_buildings(_meta(), site_eui_kbtu_per_ft2=21, k=10)
    assert len(out) == 4
    assert out.bldg_id.iloc[0] == 1


def test_extra_targets_with_floor():
    meta = _meta().assign(gas_share=[0.0, 0.3, 0.05, 0.4, 0.2])
    # same size for all, gas share decides; 0.0 is floored to 0.01 so it stays finite
    out = find_nearest_buildings(meta, targets={"gas_share": 0.04}, k=2)
    assert out.bldg_id.tolist() == [3, 1]
    with pytest.raises(ValueError, match="not in metadata"):
        find_nearest_buildings(meta, targets={"nope": 1.0})


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [({}, "at least one"), ({"sqft": 1, "k": 0}, "k must"), ({"sqft": -5}, "sqft must"), ({"site_eui_kbtu_per_ft2": 0}, "site_eui")],
)
def test_bad_inputs(kwargs, match):
    with pytest.raises(ValueError, match=match):
        find_nearest_buildings(_meta(), **kwargs)


def test_stack_upgrade_states_and_match():
    base = _meta().iloc[:4]
    led = base.assign(
        **{"out.site_energy.total.energy_consumption..kwh": base["out.site_energy.total.energy_consumption..kwh"] * 0.8},
        applicability=[True, True, False, True],
    )
    pool = stack_upgrade_states({0: base, 43: led})
    assert len(pool) == 7  # 4 baseline + 3 applicable LED states
    assert set(pool.upgrade) == {"0", "43"}
    assert "3-43" not in set(pool.state_id)
    # a building at 48 kBtu/ft2 is matched by building 2's LED state (60 * 0.8), not by a baseline building
    out = find_nearest_buildings(pool, sqft=50_000, site_eui_kbtu_per_ft2=48, k=1)
    assert out.state_id.tolist() == ["2-43"]


def test_stack_upgrade_states_empty():
    with pytest.raises(ValueError, match="empty"):
        stack_upgrade_states({})
