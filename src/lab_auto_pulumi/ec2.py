import base64
import logging

from ephemeral_pulumi_deploy import append_resource_suffix
from ephemeral_pulumi_deploy import common_tags_native
from pulumi import ComponentResource
from pulumi import Output
from pulumi import ResourceOptions
from pulumi import export
from pulumi_aws.iam import GetPolicyDocumentStatementArgs
from pulumi_aws.iam import GetPolicyDocumentStatementPrincipalArgs
from pulumi_aws.iam import get_policy_document
from pulumi_aws_native import TagArgs
from pulumi_aws_native import ec2
from pulumi_aws_native import iam

from .lib import get_org_managed_ssm_param_value

logger = logging.getLogger(__name__)


class Ec2WithRdp(ComponentResource):
    def __init__(  # noqa: PLR0913 # yes it's a lot to configure, but they're all kwargs
        self,
        *,
        name: str,
        central_networking_subnet_name: str,
        instance_type: str,
        image_id: str,
        central_networking_vpc_name: str,
        root_volume_gb: int | None = None,
        user_data: Output[str] | None = None,
        additional_instance_tags: list[TagArgs] | None = None,
    ):
        super().__init__(
            "labauto:Ec2WithRdp",
            append_resource_suffix(name),
            None,
        )
        if additional_instance_tags is None:
            additional_instance_tags = []
        resource_name = f"{name}-ec2"
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
            managed_policy_arns=["arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"],
            tags=common_tags_native(),
            opts=ResourceOptions(parent=self),
        )

        instance_profile = iam.InstanceProfile(
            append_resource_suffix(name),
            roles=[self.instance_role.role_name],  # type: ignore[reportArgumentType] # pyright thinks only inputs can be set as role names, but Outputs seem to work fine
            opts=ResourceOptions(parent=self),
        )
        sg = ec2.SecurityGroup(
            append_resource_suffix(name),
            vpc_id=get_org_managed_ssm_param_value(
                f"/org-managed/central-networking/vpcs/{central_networking_vpc_name}/id"
            ),
            group_description="Allow all outbound traffic for SSM access",
            security_group_egress=[  # TODO: see if this can be further restricted
                ec2.SecurityGroupEgressArgs(ip_protocol="-1", from_port=0, to_port=0, cidr_ip="0.0.0.0/0")
            ],
            tags=common_tags_native(),
            opts=ResourceOptions(parent=self),
        )
        self.instance = ec2.Instance(
            append_resource_suffix(name),
            instance_type=instance_type,
            image_id=image_id,
            subnet_id=get_org_managed_ssm_param_value(
                f"/org-managed/central-networking/subnets/{central_networking_subnet_name}/id"
            ),
            security_group_ids=[sg.id],
            block_device_mappings=None
            if root_volume_gb is None
            else [
                ec2.InstanceBlockDeviceMappingArgs(
                    device_name="/dev/sda1", ebs=ec2.InstanceEbsArgs(volume_size=root_volume_gb)
                )
            ],
            iam_instance_profile=instance_profile.instance_profile_name,  # type: ignore[reportArgumentType] # pyright thinks only inputs can be set as instance profile names, but Outputs seem to work fine
            tags=[TagArgs(key="Name", value=name), *additional_instance_tags, *common_tags_native()],
            user_data=None
            if user_data is None
            else user_data.apply(lambda data: base64.b64encode(data.encode("utf-8")).decode("utf-8")),
            opts=ResourceOptions(parent=self),
        )
        if user_data is not None:
            export(f"-user-data-for-{append_resource_suffix(name)}", user_data)
