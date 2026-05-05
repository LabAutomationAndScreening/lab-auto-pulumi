from typing import Any

from . import constants
from .constants import CENTRAL_NETWORKING_SSM_PREFIX
from .constants import GENERIC_CENTRAL_PRIVATE_SUBNET_NAME
from .constants import GENERIC_CENTRAL_PUBLIC_SUBNET_NAME
from .constants import GENERIC_CENTRAL_VPC_NAME
from .constants import GITHUB_DEPLOY_TOKEN_SECRET_NAME
from .constants import GITHUB_PREVIEW_TOKEN_SECRET_NAME
from .constants import MANAGEMENT_ACCOUNT_ID_PARAM_NAME
from .constants import MANUAL_IAC_SECRETS_PREFIX
from .constants import MANUAL_SECRETS_PREFIX
from .constants import ORG_MANAGED_PARAMS_AND_SECRETS_PREFIX
from .constants import SSO_INTO_EC2_PERM_SET_NAME
from .constants import TAG_KEY_FOR_SSO_INTO_EC2_ACCESS
from .constants import TAG_VALUE_FOR_DELETE_ACCESS
from .constants import TAG_VALUE_FOR_READ_ACCESS
from .constants import TAG_VALUE_FOR_WRITE_ACCESS
from .constants import USER_ACCESS_TAG_DELIMITER
from .constants import WORKLOAD_INFO_SSM_PARAM_PREFIX
from .ec2 import Ec2WithRdp
from .ec2 import ExistingSecurityGroupConfig
from .ec2 import NewSecurityGroupConfig
from .lib import AwsAccountId
from .lib import WorkloadName
from .lib import create_resource_name_safe_str
from .lib import get_manual_artifacts_bucket_name
from .lib import get_org_managed_ssm_param_value
from .lib import get_ssm_param_value
from .organization import OrganizationInfo
from .permissions import ORG_INFO
from .permissions import AwsAccountInfo
from .permissions import AwsSsoPermissionSet
from .permissions import AwsSsoPermissionSetAccountAssignments
from .permissions import OrgInfo
from .permissions import User
from .permissions import UserAttributes
from .permissions import UserInfo
from .permissions import Username
from .permissions import all_created_users
from .permissions import principal_in_org_condition
from .s3 import ManualArtifactsBucket
from .s3 import create_worm_bucket
from .workload import AwsLogicalWorkload

__all__ = [
    "CENTRAL_NETWORKING_SSM_PREFIX",
    "GENERIC_CENTRAL_PRIVATE_SUBNET_NAME",
    "GENERIC_CENTRAL_PUBLIC_SUBNET_NAME",
    "GENERIC_CENTRAL_VPC_NAME",
    "GITHUB_DEPLOY_TOKEN_SECRET_NAME",
    "GITHUB_PREVIEW_TOKEN_SECRET_NAME",
    "MANAGEMENT_ACCOUNT_ID_PARAM_NAME",
    "MANUAL_IAC_SECRETS_PREFIX",
    "MANUAL_SECRETS_PREFIX",
    "ORG_INFO",
    "ORG_MANAGED_PARAMS_AND_SECRETS_PREFIX",
    "SSO_INTO_EC2_PERM_SET_NAME",
    "TAG_KEY_FOR_SSO_INTO_EC2_ACCESS",
    "TAG_VALUE_FOR_DELETE_ACCESS",
    "TAG_VALUE_FOR_READ_ACCESS",
    "TAG_VALUE_FOR_WRITE_ACCESS",
    "USER_ACCESS_TAG_DELIMITER",
    "WORKLOAD_INFO_SSM_PARAM_PREFIX",
    "AwsAccountId",
    "AwsAccountInfo",
    "AwsLogicalWorkload",
    "AwsSsoPermissionSet",
    "AwsSsoPermissionSetAccountAssignments",
    "Ec2WithRdp",
    "ExistingSecurityGroupConfig",
    "ManualArtifactsBucket",
    "NewSecurityGroupConfig",
    "OrgInfo",
    "OrganizationInfo",
    "User",
    "UserAttributes",
    "UserInfo",
    "Username",
    "WorkloadName",
    "all_created_users",
    "constants",
    "create_resource_name_safe_str",
    "create_worm_bucket",
    "get_manual_artifacts_bucket_name",
    "get_org_managed_ssm_param_value",
    "get_ssm_param_value",
    "principal_in_org_condition",
]


def __getattr__(name: str) -> Any:  # noqa: ANN401 # In this case it can in fact by anything so Any is appropriate
    if name == "ORG_MANAGED_SSM_PARAM_PREFIX":
        from .constants import (  # noqa:PLC0415 # Must be here so that we can verify the deprecation in a test otherwise it happens at init time and we miss it.
            ORG_MANAGED_SSM_PARAM_PREFIX,
        )

        return ORG_MANAGED_SSM_PARAM_PREFIX
    raise AttributeError(f"module {__name__} has no attribute {name}")  # noqa:TRY003 # this is infact an attribute error. Its fine
