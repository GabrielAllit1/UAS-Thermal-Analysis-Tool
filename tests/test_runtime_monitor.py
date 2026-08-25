import time

from uas_thermal.application.autopilot import RuntimeSnapshot
from uas_thermal.application.runtime_monitor import RuntimeMonitor


def _snapshot():
    return RuntimeSnapshot(
        ai_available=False,
        model_names=(),
        vision_models=(),
        orthomosaic_backends=(("native-geotiff", True),),
        ai_error="test",
    )


def test_runtime_refresh_returns_immediately_while_scanner_runs():
    def slow_scanner():
        time.sleep(0.15)
        return _snapshot()

    monitor = RuntimeMonitor(slow_scanner, min_interval_s=0)
    started = time.perf_counter()
    assert monitor.request_refresh() is True
    elapsed = time.perf_counter() - started
    assert elapsed < 0.05
    assert monitor.refreshing is True
    monitor.close()


def test_runtime_monitor_coalesces_refreshes_and_publishes_result():
    calls = 0

    def scanner():
        nonlocal calls
        calls += 1
        time.sleep(0.03)
        return _snapshot()

    monitor = RuntimeMonitor(scanner, min_interval_s=0)
    assert monitor.request_refresh() is True
    assert monitor.request_refresh() is False

    update = None
    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline and update is None:
        update = monitor.poll()
        time.sleep(0.005)

    assert update is not None
    assert update.snapshot is not None
    assert update.snapshot.quantitative_stitch_available is True
    assert calls == 1
    monitor.close()
