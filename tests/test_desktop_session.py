from pathlib import Path

from uas_thermal.application.desktop import DesktopSession


def test_desktop_session_tracks_sources_without_qt():
    session = DesktopSession()
    session.set_sources(["a.tif", "b.tif"])
    assert session.sources == [Path("a.tif"), Path("b.tif")]
    assert session.artifacts == []
