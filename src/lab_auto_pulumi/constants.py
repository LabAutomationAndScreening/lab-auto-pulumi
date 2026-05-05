import warnings
from typing import Any

GENERIC_CENTRAL_VPC_NAME = "generic"
GENERIC_CENTRAL_PUBLIC_SUBNET_NAME = "generic-public"
GENERIC_CENTRAL_PRIVATE_SUBNET_NAME = "generic-private"
ORG_MANAGED_PARAMS_AND_SECRETS_PREFIX = "/org-managed"
_DEPRECATED_ORG_MANAGED_SSM_PARAM_PREFIX = ORG_MANAGED_PARAMS_AND_SECRETS_PREFIX
WORKLOAD_INFO_SSM_PARAM_PREFIX = f"{ORG_MANAGED_PARAMS_AND_SECRETS_PREFIX}/logical-workloads"
MANAGEMENT_ACCOUNT_ID_PARAM_NAME = f"{ORG_MANAGED_PARAMS_AND_SECRETS_PREFIX}/management-account-id"

CENTRAL_NETWORKING_SSM_PREFIX = f"{ORG_MANAGED_PARAMS_AND_SECRETS_PREFIX}/central-networking"

MANUAL_SECRETS_PREFIX = "/manually-entered-secrets"
MANUAL_IAC_SECRETS_PREFIX = f"{MANUAL_SECRETS_PREFIX}/iac"
GITHUB_DEPLOY_TOKEN_SECRET_NAME = f"{MANUAL_IAC_SECRETS_PREFIX}/github-deploy-access-token"
GITHUB_PREVIEW_TOKEN_SECRET_NAME = f"{MANUAL_IAC_SECRETS_PREFIX}/github-preview-access-token"
IAC_DEPLOY_TOKENS_SECRETS_PREFIX = f"{MANUAL_IAC_SECRETS_PREFIX}/deploy-tokens"
IAC_PREVIEW_TOKEN_SECRETS_PREFIX = f"{MANUAL_IAC_SECRETS_PREFIX}/preview-tokens"

USER_ACCESS_TAG_DELIMITER = "--"

SSO_INTO_EC2_PERM_SET_NAME = "SsoIntoEc2"
TAG_KEY_FOR_SSO_INTO_EC2_ACCESS = "SsoIntoEc2AccessLevel"  # note: S3 Buckets and Objects do not support condition keys, so use a bucket policy instead
TAG_VALUE_FOR_READ_ACCESS = "Read"
TAG_VALUE_FOR_WRITE_ACCESS = "Write"
TAG_VALUE_FOR_DELETE_ACCESS = "Delete"


def __getattr__(name: str) -> Any:  # noqa: ANN401 # In this case it can in fact by anything so Any is appropriate
    # https://peps.python.org/pep-0562/
    if name == "ORG_MANAGED_SSM_PARAM_PREFIX":
        warnings.warn(
            "'ORG_MANAGED_SSM_PARAM_PREFIX' has been deprecated and will be removed in the future. Use 'ORG_MANAGED_PARAMS_AND_SECRETS_PREFIX'",
            DeprecationWarning,
            stacklevel=2,
        )
        return globals()["_DEPRECATED_ORG_MANAGED_SSM_PARAM_PREFIX"]
    raise AttributeError(f"module {__name__} has no attribute {name}")  # noqa:TRY003 # this is infact an attribute error. Its fine
