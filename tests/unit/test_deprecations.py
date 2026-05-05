import warnings

import pytest


def test_deprecation_warning_in_place():
    warnings.resetwarnings()

    with pytest.warns(
        DeprecationWarning,
        match="'ORG_MANAGED_SSM_PARAM_PREFIX' has been deprecated and will be removed in the future. Use 'ORG_MANAGED_PARAMS_AND_SECRETS_PREFIX'",
    ):
        from lab_auto_pulumi import (  # noqa:PLC0415 # this import has to be here so that we can catch the warning that it produces
            ORG_MANAGED_SSM_PARAM_PREFIX,
        )

    assert ORG_MANAGED_SSM_PARAM_PREFIX == "/org-managed"
