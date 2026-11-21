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
