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
