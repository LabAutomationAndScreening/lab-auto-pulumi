# ============== WARNING ==============================================================================
# File is managed by copier template: gh:LabAutomationAndScreening/copier-python-package-template
# See .config/.copier-managed-files.json for details.
#
# You are welcome to make changes to this file in your repo if they are custom to your project,
# but if the change should be shared with other projects, please backport it to the template repo.
# =====================================================================================================
import asyncio
import logging
from collections.abc import Callable
from collections.abc import Generator
from concurrent.futures import Future
from concurrent.futures import ThreadPoolExecutor
from typing import override

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
    loop.set_default_executor(ImmediateExecutor())
    yield loop
    loop.close()
    asyncio.set_event_loop(None)


class ImmediateExecutor(ThreadPoolExecutor):
    """Run submitted callables inline on the calling thread instead of on pool threads.

    Pulumi's SDK sends every mock monitor call through `loop.run_in_executor(None, ...)`. On pool threads the mock
    monitor calls `_ensure_event_loop()`, creating a thread-local loop that is never closed; those loops are
    garbage-collected at interpreter exit after their self-pipe is gone, raising
    `ValueError: Invalid file descriptor: -1` from `BaseEventLoop.__del__`. The threading also makes mock tests
    flaky. Pulumi's own mock tests use the same workaround: https://github.com/pulumi/pulumi/pull/7666

    Subclasses ThreadPoolExecutor because `loop.set_default_executor` rejects any other executor type. No worker
    thread is ever started because `submit` never delegates to the pool.
    """

    def __init__(self) -> None:
        super().__init__(max_workers=1)

    @override
    def submit[**P, T](self, fn: Callable[P, T], /, *args: P.args, **kwargs: P.kwargs) -> Future[T]:
        future = Future[T]()
        try:
            result = fn(*args, **kwargs)
        except BaseException as e:  # noqa: BLE001 # mirrors ThreadPoolExecutor's worker, which routes every exception into the future for the awaiting caller to re-raise
            future.set_exception(e)
        else:
            future.set_result(result)
        return future
