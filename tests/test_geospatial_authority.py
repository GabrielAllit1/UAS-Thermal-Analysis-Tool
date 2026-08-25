import pytest

from uas_thermal.geospatial.transforms import crs_warning, map_to_pixel, transform_point


def test_epsg4326_identity_is_allowed():
    assert transform_point(-82.0, 28.0, "EPSG:4326") == (-82.0, 28.0)


def test_internally_inconsistent_local_crs_is_blocked():
    crs = 'LOCAL_CS["NAD83(2011) / Georgia West (ftUS)",UNIT["metre",1]]'
    assert crs_warning(crs) is not None
    with pytest.raises(ValueError, match="coordinate transform blocked"):
        transform_point(2340427.0, 683476.0, crs)


def test_map_to_pixel_inverts_simple_affine():
    transform = (2.0, 0.0, 100.0, 0.0, -2.0, 200.0)
    x, y = map_to_pixel(120.0, 180.0, transform)
    assert x == 10.0
    assert y == 10.0
