import shutil
from pathlib import Path

import pytest

from hunter.spec import SpecError, load_hunt, load_profile

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def test_example_profile_loads(tmp_path):
    shutil.copytree(EXAMPLES, tmp_path / "someone")
    profile = load_profile("someone", profiles_dir=tmp_path)
    sofa = profile.hunts[0]
    assert sofa.max_price == 100
    assert sofa.size == {"width_max": 200, "chaise_max": 200}
    assert "RIGHT when you are sitting" in sofa.musts[0]


def test_unknown_site_is_rejected(tmp_path):
    hunt = tmp_path / "bad.toml"
    hunt.write_text('name="x"\nsearches=["x"]\nmax_price=1\nmax_distance=1\nsites=["craigslist"]\n')
    with pytest.raises(SpecError, match="craigslist"):
        load_hunt(hunt)


def test_missing_profile_explains_fix(tmp_path):
    with pytest.raises(SpecError, match="Copy examples"):
        load_profile("nobody", profiles_dir=tmp_path)


def test_profile_and_hunt_round_trip(tmp_path):
    from hunter.spec import Home, Hunt, create_profile, list_profiles, save_hunt
    create_profile("sam", Home(postcode="CR0 1AA", gumtree_area="croydon"), tmp_path)
    hunt = Hunt(slug="desk", name='Standing "desk"', searches=["standing desk"], max_price=80.5,
                max_distance=5, sites=["gumtree"], size={"width_max": 140},
                musts=["Electric, not crank"], avoid=["glass top"], gumtree_category="for-sale/x")
    save_hunt("sam", hunt, tmp_path)
    loaded = load_profile("sam", tmp_path)
    assert list_profiles(tmp_path) == ["sam"]
    assert loaded.home.gumtree_area == "croydon"
    assert loaded.hunts[0] == hunt


def test_bad_names_are_refused(tmp_path):
    from hunter.spec import Home, create_profile
    with pytest.raises(SpecError):
        create_profile("../evil", Home(postcode="X"), tmp_path)
