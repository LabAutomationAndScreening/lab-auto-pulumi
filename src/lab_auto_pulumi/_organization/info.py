from functools import cached_property

from pulumi_aws.organizations import AwaitableGetOrganizationResult
from pulumi_aws.organizations import get_organization


class OrganizationInfo:
    @cached_property
    def organization(self) -> AwaitableGetOrganizationResult:
        return get_organization()

    @cached_property
    def id(self) -> str:
        return self.organization.id
