from uas_thermal.geospatial.world_file import WorldFile


def test_world_file_pixel_transform():
    world = WorldFile(2.0, 0.0, 0.0, -2.0, 100.0, 200.0)
    assert world.pixel_to_map(3, 4) == (106.0, 192.0)
