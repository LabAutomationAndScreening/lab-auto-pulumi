import base64
import logging

from ephemeral_pulumi_deploy import append_resource_suffix
from ephemeral_pulumi_deploy import common_tags_native
from pulumi import ComponentResource
from pulumi import Output
from pulumi import Resource
from pulumi import ResourceOptions
from pulumi import export
from pulumi_aws.iam import GetPolicyDocumentStatementArgs
from pulumi_aws.iam import GetPolicyDocumentStatementPrincipalArgs
from pulumi_aws.iam import get_policy_document
from pulumi_aws_native import TagArgs
from pulumi_aws_native import ec2
from pulumi_aws_native import iam

from .constants import CENTRAL_NETWORKING_SSM_PREFIX
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
        root_volume_gb: int = 30,
        user_data: Output[str]
        | None = None,  # On Windows EC2, Userdata script shows up here: C:\Windows\system32\config\systemprofile\AppData\Local\Temp\Amazon\EC2-Windows\Launch\InvokeUserData\UserScript.ps1.  You may need to start just at system32 and navigate down, because it will keep asking for permissions
        additional_instance_tags: list[TagArgs] | None = None,
        security_group_description: str = "Allow all outbound traffic for SSM access",
        ingress_rules: list[ec2.SecurityGroupIngressArgs] | None = None,
        persist_user_data: bool = False,  # if false, then user data changes will result in replacing the instance (because new user data won't take effect unless the instance is replaced). if true, then you can replace the user data, but it will force an immediate restart of the EC2...which may not actually show up in the Pulumi plan
        # TODO: maybe ensure that the persist flag in the user data XML has been set, or add it automatically if it hasn't (when persist_user_data set to true)
        # remember for Windows Instances, if you create an ingress rule, you also need to create a Firewall inbound rule on the EC2 instance itself in order for it to actually be accessible
        parent: Resource | None = None,
    ):
        super().__init__("labauto:Ec2WithRdp", append_resource_suffix(name), None, opts=ResourceOptions(parent=parent))
        replace_on_changes = ["user_data"] if not persist_user_data else []
        self.name = name
        if ingress_rules is None:
            ingress_rules = []
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
        self.security_group = ec2.SecurityGroup(
            append_resource_suffix(name),
            vpc_id=get_org_managed_ssm_param_value(
                f"{CENTRAL_NETWORKING_SSM_PREFIX}/vpcs/{central_networking_vpc_name}/id"
            ),
            group_description=security_group_description,
            tags=[TagArgs(key="Name", value=name), *common_tags_native()],
            opts=ResourceOptions(parent=self),
        )
        for idx, rule_args in enumerate(ingress_rules):
            _ = ec2.SecurityGroupIngress(
                append_resource_suffix(f"{name}-ingress-{idx}", max_length=190),
                opts=ResourceOptions(parent=self.security_group),
                ip_protocol=rule_args.ip_protocol,
                from_port=rule_args.from_port,
                to_port=rule_args.to_port,
                source_security_group_id=rule_args.source_security_group_id,
                group_id=self.security_group.id,
            )
        _ = ec2.SecurityGroupEgress(  # TODO: see if this can be further restricted
            append_resource_suffix(f"{name}-egress", max_length=190),
            opts=ResourceOptions(parent=self.security_group),
            ip_protocol="-1",
            from_port=0,
            to_port=0,
            cidr_ip="0.0.0.0/0",
            group_id=self.security_group.id,
        )
        self.instance = ec2.Instance(
            append_resource_suffix(name),
            instance_type=instance_type,
            image_id=image_id,
            subnet_id=get_org_managed_ssm_param_value(
                f"{CENTRAL_NETWORKING_SSM_PREFIX}/subnets/{central_networking_subnet_name}/id"
            ),
            security_group_ids=[self.security_group.id],
            block_device_mappings=[
                ec2.InstanceBlockDeviceMappingArgs(
                    device_name="/dev/sda1", ebs=ec2.InstanceEbsArgs(volume_size=root_volume_gb, volume_type="gp3")
                )
            ],
            iam_instance_profile=instance_profile.instance_profile_name,  # type: ignore[reportArgumentType] # pyright thinks only inputs can be set as instance profile names, but Outputs seem to work fine
            tags=[TagArgs(key="Name", value=name), *additional_instance_tags, *common_tags_native()],
            user_data=None
            if user_data is None
            else user_data.apply(lambda data: base64.b64encode(data.encode("utf-8")).decode("utf-8")),
            opts=ResourceOptions(parent=self, replace_on_changes=replace_on_changes),
        )
        if user_data is not None:
            export(f"-user-data-for-{append_resource_suffix(name)}", user_data)
