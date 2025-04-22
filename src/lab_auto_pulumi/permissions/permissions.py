import logging

from ephemeral_pulumi_deploy import common_tags
from ephemeral_pulumi_deploy import get_config_str
from pulumi import ComponentResource
from pulumi import ResourceOptions
from pulumi_aws import identitystore as identitystore_classic
from pulumi_aws import ssoadmin

from .lib import ORG_INFO
from .lib import AwsAccountInfo
from .lib import UserInfo
from .lib import Username

logger = logging.getLogger(__name__)


class UserNotFoundInIdentityStoreError(ValueError):
    def __init__(self, username: Username):
        super().__init__(f"User {username!r} not found in the Identity Store")


def lookup_user_id(username: Username) -> str:
    """Convert a username name into an AWS SSO User ID."""
    try:
        user_result = identitystore_classic.get_user(
            alternate_identifier=identitystore_classic.GetUserAlternateIdentifierArgs(
                unique_attribute=identitystore_classic.GetUserAlternateIdentifierUniqueAttributeArgs(
                    attribute_path="UserName", attribute_value=username
                )
            ),
            identity_store_id=ORG_INFO.identity_store_id,
        )
    except Exception as e:  # the exception Pulumi throws is just Exception, it's not a more specific subclass
        if "ResourceNotFoundException: USER not found" in str(e):
            raise UserNotFoundInIdentityStoreError(username) from e
        raise
    return user_result.user_id


class AwsSsoPermissionSet(ComponentResource):
    def __init__(
        self,
        *,
        name: str,
        description: str,
        managed_policies: list[str] | None = None,
        inline_policy: str | None = None,
        relay_state: str | None = None,
    ):
        super().__init__("labauto:AwsSsoPermissionSet", name, None)
        if relay_state is None:
            relay_state = f"https://{get_config_str('proj:aws_org_home_region')}.console.aws.amazon.com/console/home"
        if managed_policies is None:
            managed_policies = []
        self.name = name
        permission_set = ssoadmin.PermissionSet(
            name,
            instance_arn=ORG_INFO.sso_instance_arn,
            name=name,
            description=description,
            session_duration="PT12H",
            opts=ResourceOptions(parent=self),
            relay_state=relay_state,
            tags=common_tags(),
        )
        self.permission_set_arn = permission_set.arn
        for policy_name in managed_policies:
            _ = ssoadmin.ManagedPolicyAttachment(
                f"{name}-{policy_name}",
                instance_arn=ORG_INFO.sso_instance_arn,
                managed_policy_arn=f"arn:aws:iam::aws:policy/{policy_name}",
                permission_set_arn=self.permission_set_arn,
                opts=ResourceOptions(parent=self),
            )
        if inline_policy is not None:
            _ = ssoadmin.PermissionSetInlinePolicy(
                f"{name}-inline-policy",
                instance_arn=ORG_INFO.sso_instance_arn,
                permission_set_arn=self.permission_set_arn,
                inline_policy=inline_policy,
                opts=ResourceOptions(parent=self),
            )
        self.register_outputs(
            {
                "permission_set_arn": self.permission_set_arn,
            }
        )


def _create_unique_userinfo_list(users: list[UserInfo]) -> list[UserInfo]:
    unique_user_infos: dict[Username, UserInfo] = {}
    for user_info in users:
        if user_info.username not in unique_user_infos:
            unique_user_infos[user_info.username] = user_info
            continue
        info_in_dict = unique_user_infos[user_info.username]
        if user_info == info_in_dict:
            continue
        raise ValueError(f"Duplicate user info for {user_info!r} and {info_in_dict!r}")  # noqa: TRY003 # not worth creating a custom exception until we test this # TODO: unit test this
    return list(unique_user_infos.values())


class AwsSsoPermissionSetAccountAssignments(ComponentResource):
    def __init__(
        self,
        *,
        account_info: AwsAccountInfo,
        permission_set: AwsSsoPermissionSet,
        users: list[UserInfo] | None = None,
    ):
        if users is None:
            users = []
        resource_name = f"{permission_set.name}-{account_info.name}"
        super().__init__(
            "labauto:AwsSsoPermissionSetAccountAssignments",
            resource_name,
            None,
        )
        user_infos = _create_unique_userinfo_list(users)

        for user_info in user_infos:
            try:
                principal_id = lookup_user_id(user_info.username)
            except UserNotFoundInIdentityStoreError as e:
                logger.warning(
                    f"Skipping user {user_info.username!r} for {resource_name} permission set assignment because {e}"
                )
                continue
            _ = ssoadmin.AccountAssignment(
                f"{resource_name}-{user_info.username}",
                instance_arn=ORG_INFO.sso_instance_arn,
                permission_set_arn=permission_set.permission_set_arn,
                principal_id=principal_id,
                principal_type="USER",
                target_id=account_info.id,
                target_type="AWS_ACCOUNT",
                opts=ResourceOptions(parent=self),
            )
