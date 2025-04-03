from functools import cached_property
from typing import Any
from typing import override

from pulumi_aws import identitystore as identitystore_classic
from pulumi_aws import ssoadmin
from pydantic import BaseModel
from pydantic import Field


class AwsAccountInfo(BaseModel, frozen=True):
    version: str = "0.0.1"
    id: str
    name: str


class OrgInfo(BaseModel):
    @cached_property
    def sso_instances(self) -> ssoadmin.AwaitableGetInstancesResult:
        instances = ssoadmin.get_instances()
        assert len(instances.arns) == 1, f"Expected a single AWS SSO instance to exist, but found {len(instances.arns)}"
        return instances

    @cached_property
    def sso_instance_arn(self) -> str:
        return self.sso_instances.arns[0]

    @cached_property
    def identity_store_id(self) -> str:
        all_ids = self.sso_instances.identity_store_ids
        assert len(all_ids) == 1, f"Expected a single identity store id, but found {len(all_ids)}"
        return self.sso_instances.identity_store_ids[0]


type Username = str
ORG_INFO = OrgInfo()


class UserAttributes(BaseModel):
    exclude_from_manual_artifacts: bool = False
    exclude_from_cloud_courier: bool = False


class UserInfo(BaseModel):
    username: Username
    attributes: UserAttributes = Field(default_factory=UserAttributes)


all_created_users: dict[Username, UserInfo] = {}


class User(BaseModel):  # NOT RECOMMENDED TO USE THIS IF YOU HAVE AN EXTERNAL IDENTITY PROVIDER!!
    first_name: str
    last_name: str
    email: str
    user_attributes: UserAttributes = Field(default_factory=UserAttributes)
    _user: identitystore_classic.User | None = None

    @override
    def model_post_init(self, _: Any) -> None:
        all_created_users[self.username] = UserInfo(username=self.username, attributes=self.user_attributes)
        self._user = identitystore_classic.User(
            f"{self.first_name}-{self.last_name}",
            identity_store_id=ORG_INFO.identity_store_id,
            display_name=f"{self.first_name} {self.last_name}",
            user_name=self.username,
            name=identitystore_classic.UserNameArgs(
                given_name=self.first_name,
                family_name=self.last_name,
            ),
            emails=identitystore_classic.UserEmailsArgs(primary=True, value=self.email),
        )

    @property
    def username(self) -> Username:
        return f"{self.first_name}.{self.last_name}"

    @property
    def user(self) -> identitystore_classic.User:
        assert self._user is not None
        return self._user

    @property
    def user_info(self) -> UserInfo:
        return UserInfo(username=self.username, attributes=self.user_attributes)
