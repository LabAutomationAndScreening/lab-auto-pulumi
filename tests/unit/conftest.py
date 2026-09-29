# ============== WARNING ==============================================================================
# File is managed by copier template: gh:LabAutomationAndScreening/copier-python-package-template
# See .config/.copier-managed-files.json for details.
#
# You are welcome to make changes to this file in your repo if they are custom to your project,
# but if the change should be shared with other projects, please backport it to the template repo.
# =====================================================================================================
import asyncio
import logging
from collections.abc import Generator
from unittest import mock

import pytest

logger = logging.getLogger(__name__)


def pytest_configure(
    config: pytest.Config,
) -> None:
    """Configure pytest itself, such as logging levels."""


@pytest.fixture(autouse=True)
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    # Python 3.14 removed the implicit event loop creation in asyncio.get_event_loop().
    # pulumi.runtime.test relies on that implicit creation, so we create one explicitly
    # before each test and tear it down after.
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()
    asyncio.set_event_loop(None)


@pytest.fixture(autouse=True, scope="session")
def close_worker_thread_event_loops() -> Generator[None, None, None]:
    """Close event loops that Pulumi's mock monitor creates on its worker threads.

    The mock monitor serves Invoke/ReadResource/RegisterResource on thread-pool threads and calls
    `_ensure_event_loop()` on each, which creates a thread-local loop that is never closed. Left open, those
    loops are garbage-collected at interpreter exit after their self-pipe is gone, raising
    `ValueError: Invalid file descriptor: -1` from `BaseEventLoop.__del__`, which pytest reports as a
    PytestUnraisableExceptionWarning.

    Upstream, https://github.com/pulumi/pulumi/issues/7663 proposes removing the SDK's thread-pool hops, which
    would make this unnecessary.
    """
    created_loops: list[asyncio.AbstractEventLoop] = []
    original_new_event_loop = asyncio.new_event_loop

    def tracking_new_event_loop() -> asyncio.AbstractEventLoop:
        loop = original_new_event_loop()
        created_loops.append(loop)
        return loop

    with mock.patch.object(asyncio, asyncio.new_event_loop.__name__, tracking_new_event_loop):
        yield
    for loop in created_loops:
        if not loop.is_closed():
            loop.close()
