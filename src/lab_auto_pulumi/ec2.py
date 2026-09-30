import base64
import logging
from typing import Self

from ephemeral_pulumi_deploy import append_resource_suffix
from ephemeral_pulumi_deploy import common_tags
from ephemeral_pulumi_deploy import common_tags_native
from pulumi import ComponentResource
from pulumi import InvokeOutputOptions
from pulumi import Output
from pulumi import Resource
from pulumi import ResourceOptions
from pulumi import export
from pulumi_aws import vpc
from pulumi_aws.iam import GetPolicyDocumentStatementArgs
from pulumi_aws.iam import GetPolicyDocumentStatementPrincipalArgs
from pulumi_aws.iam import get_policy_document
from pulumi_aws_native import TagArgs
from pulumi_aws_native import ec2
from pulumi_aws_native import get_partition_output
from pulumi_aws_native import get_region_output
from pulumi_aws_native import iam
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import model_validator

from .constants import CENTRAL_NETWORKING_SSM_PREFIX
from .lib import get_org_managed_ssm_param_value

logger = logging.getLogger(__name__)


class SecurityGroupIngressRuleConfig(BaseModel):
    """One inbound rule on the instance's security group, backed by the classic `aws.vpc.SecurityGroupIngressRule`.

    Exactly one of `source_security_group_id` or `cidr_ipv4` must be set. The classic resource is used instead of
    the aws-native (CloudFormation) one because CloudFormation silently adopts an existing identical rule on create,
    which lets two Pulumi resources own one AWS rule; the classic provider fails loudly on duplicates instead.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    description: str = Field(min_length=1)
    ip_protocol: str = "tcp"
    from_port: int
    to_port: int
    source_security_group_id: Output[str] | str | None = None
    cidr_ipv4: str | None = None

    @model_validator(mode="after")
    def _exactly_one_source(self) -> Self:
        if (self.source_security_group_id is None) == (self.cidr_ipv4 is None):
            raise ValueError("exactly one of source_security_group_id or cidr_ipv4 must be set")  # noqa: TRY003 # pydantic surfaces the message directly to the caller
        return self


class NewSecurityGroupConfig(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    central_networking_vpc_name: str
    description: str = "Allow all outbound traffic for SSM access"
    ingress_rules: list[SecurityGroupIngressRuleConfig] = []


class ExistingSecurityGroupConfig(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    security_group_id: Output[str]


type _PolicyStatement = dict[str, str | list[str]]
type _PolicyDocument = dict[str, str | list[_PolicyStatement]]


def _dcv_license_policy(*, partition: Output[str], parent: Resource) -> Output[_PolicyDocument]:
    # https://docs.aws.amazon.com/dcv/latest/adminguide/setting-up-license.html
    return Output.all(
        partition=partition, region=get_region_output(opts=InvokeOutputOptions(parent=parent)).region
    ).apply(
        lambda args: {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": ["s3:GetObject"],
                    "Resource": [f"arn:{args['partition']}:s3:::dcv-license.{args['region']}/*"],
                }
            ],
        }
    )


class Ec2WithRdp(ComponentResource):
    def __init__(  # noqa: PLR0913 # yes it's a lot to configure, but they're all kwargs
        self,
        *,
        name: str,
        central_networking_subnet_name: str,
        instance_type: str,
        image_id: str,
        security_group_config: NewSecurityGroupConfig | ExistingSecurityGroupConfig,
        root_volume_gb: int = 30,
        user_data: Output[str]
        | None = None,  # On Windows EC2, Userdata script shows up here: C:\Windows\system32\config\systemprofile\AppData\Local\Temp\Amazon\EC2-Windows\Launch\InvokeUserData\UserScript.ps1.  You may need to start just at system32 and navigate down, because it will keep asking for permissions
        additional_instance_tags: list[TagArgs] | None = None,
        instance_ignore_changes: list[str] | None = None,
        export_user_data: bool = True,
        persist_user_data: bool = False,  # if false, then user data changes will result in replacing the instance (because new user data won't take effect unless the instance is replaced). if true, then you can replace the user data, but it will force an immediate restart of the EC2...which may not actually show up in the Pulumi plan
        # TODO: maybe ensure that the persist flag in the user data XML has been set, or add it automatically if it hasn't (when persist_user_data set to true)
        # remember for Windows Instances, if you create an ingress rule, you also need to create a Firewall inbound rule on the EC2 instance itself in order for it to actually be accessible
        grant_dcv_license_access: bool = False,
        parent: Resource | None = None,
    ):
        super().__init__("labauto:Ec2WithRdp", append_resource_suffix(name), None, opts=ResourceOptions(parent=parent))
        replace_on_changes: list[str] = []
        if not persist_user_data:
            replace_on_changes = ["user_data"]
        self.name = name
        if additional_instance_tags is None:
            additional_instance_tags = []
        resource_name = f"{name}-ec2"
        partition = get_partition_output(opts=InvokeOutputOptions(parent=self)).partition
        self.instance_role = iam.Role(
            append_resource_suffix(resource_name),
            assume_role_policy_document=get_policy_document(
                statements=[
                    GetPolicyDocumentStatementArgs(
                        effect="Allow",
                        actions=["sts:AssumeRole"],
                        principals=[
                            GetPolicyDocumentStatementPrincipalArgs(type="Service", identifiers=["ec2.amazonaws.com"])
                        ],
                    )
                ]
            ).json,
            managed_policy_arns=[Output.concat("arn:", partition, ":iam::aws:policy/AmazonSSMManagedInstanceCore")],
            tags=common_tags_native(),
            opts=ResourceOptions(parent=self),
        )
        if grant_dcv_license_access:
            _ = iam.RolePolicy(
                append_resource_suffix(f"{name}-dcv-license", max_length=99),
                role_name=self.instance_role.role_name,
                policy_document=_dcv_license_policy(partition=partition, parent=self),
                opts=ResourceOptions(parent=self.instance_role),
            )

        instance_profile = iam.InstanceProfile(  # pyrefly: ignore[no-matching-overload] # role_name is typed Output[str | None] because it's optional on input, but AWS always generates one once the role exists
            append_resource_suffix(name),
            roles=[self.instance_role.role_name],
            opts=ResourceOptions(parent=self),
        )
        if isinstance(security_group_config, ExistingSecurityGroupConfig):
            self.security_group = ec2.SecurityGroup.get(
                append_resource_suffix(name),
                security_group_config.security_group_id,
                opts=ResourceOptions(parent=self),
            )
            resolved_security_group_id = self.security_group.id
        else:
            self.security_group = ec2.SecurityGroup(
                append_resource_suffix(name),
                vpc_id=get_org_managed_ssm_param_value(
                    f"{CENTRAL_NETWORKING_SSM_PREFIX}/vpcs/{security_group_config.central_networking_vpc_name}/id"
                ),
                group_description=security_group_config.description,
                tags=[TagArgs(key="Name", value=name), *common_tags_native()],
                opts=ResourceOptions(
                    parent=self,
                    replace_on_changes=[  # these are immutable  https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-ec2-securitygroup.html
                        "groupDescription",
                        "groupName",
                        "vpcId",
                    ],
                    # `pulumi refresh` on the aws-native SecurityGroup projects every live rule into these inputs, and
                    # the next `up` then sends a remove patch that revokes the whole group. Rules are managed only
                    # through the standalone resources below, so never let these inputs drift.
                    ignore_changes=["securityGroupIngress", "securityGroupEgress"],
                ),
            )
            for idx, rule in enumerate(security_group_config.ingress_rules):
                _ = vpc.SecurityGroupIngressRule(
                    append_resource_suffix(
                        f"{name}-in-{rule.ip_protocol}-{rule.from_port}-{rule.to_port}-{idx}", max_length=190
                    ),
                    security_group_id=self.security_group.id,
                    description=rule.description,
                    ip_protocol=rule.ip_protocol,
                    from_port=rule.from_port,
                    to_port=rule.to_port,
                    referenced_security_group_id=rule.source_security_group_id,
                    cidr_ipv4=rule.cidr_ipv4,
                    tags=common_tags(),
                    opts=ResourceOptions(parent=self.security_group),
                )
            _ = vpc.SecurityGroupEgressRule(  # TODO: see if this can be further restricted
                append_resource_suffix(f"{name}-out-all", max_length=190),
                security_group_id=self.security_group.id,
                description="Allow all outbound traffic",
                ip_protocol="-1",
                cidr_ipv4="0.0.0.0/0",
                tags=common_tags(),
                opts=ResourceOptions(parent=self.security_group),
            )
            resolved_security_group_id = self.security_group.id
        self.instance = ec2.Instance(
            append_resource_suffix(name),
            instance_type=instance_type,
            image_id=image_id,
            subnet_id=get_org_managed_ssm_param_value(
                f"{CENTRAL_NETWORKING_SSM_PREFIX}/subnets/{central_networking_subnet_name}/id"
            ),
            security_group_ids=[resolved_security_group_id],
            block_device_mappings=[
                ec2.InstanceBlockDeviceMappingArgs(
                    device_name="/dev/sda1", ebs=ec2.InstanceEbsArgs(volume_size=root_volume_gb, volume_type="gp3")
                )
            ],
            iam_instance_profile=instance_profile.instance_profile_name,
            # TODO: if additional_instance_tags also contains a "Name" tag, the instance gets two Name tags; decide whether the caller's value should replace the default or be rejected with a clear ValueError
            tags=[TagArgs(key="Name", value=name), *additional_instance_tags, *common_tags_native()],
            user_data=None
            if user_data is None
            else user_data.apply(lambda data: base64.b64encode(data.encode("utf-8")).decode("utf-8")),
            opts=ResourceOptions(
                parent=self, replace_on_changes=replace_on_changes, ignore_changes=instance_ignore_changes
            ),
        )
        if user_data is not None and export_user_data:
            export(f"-user-data-for-{append_resource_suffix(name)}", user_data)
