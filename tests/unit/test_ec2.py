import base64
import json
from collections.abc import Sequence
from typing import Any
from unittest import mock

import pulumi
import pulumi.runtime
import pytest
from pulumi_aws_native import TagArgs
from pulumi_aws_native import ec2

from lab_auto_pulumi.ec2 import Ec2WithRdp
from lab_auto_pulumi.ec2 import ExistingSecurityGroupConfig
from lab_auto_pulumi.ec2 import NewSecurityGroupConfig

_pulumi_test = pulumi.runtime.test  # type: ignore[reportUnknownMemberType] # pulumi.runtime.test is partially typed in the Pulumi SDK; alias avoids repeating the ignore on every test


class Ec2Mocks(pulumi.runtime.Mocks):
    def __init__(self) -> None:
        super().__init__()
        self.created_resources: list[pulumi.runtime.MockResourceArgs] = []

    def new_resource(self, args: pulumi.runtime.MockResourceArgs) -> tuple[str, dict[str, Any]]:  # type: ignore[override] # pyright infers Optional[str] for id but str is always safe here
        self.created_resources.append(args)
        resource_id = args.resource_id or f"{args.name}-id"
        return (resource_id, args.inputs)  # type: ignore[return-value] # Pulumi SDK types inputs as dict[Unknown, Unknown]

    def call(self, args: pulumi.runtime.MockCallArgs) -> dict[str, Any]:  # type: ignore[override] # pyright infers tuple[dict, Optional[list]] but plain dict is accepted
        if args.token == "aws:iam/getPolicyDocument:getPolicyDocument":  # noqa:S105 # definitely not a password
            return {
                "json": json.dumps(
                    {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Effect": "Allow",
                                "Action": "sts:AssumeRole",
                                "Principal": {"Service": "ec2.amazonaws.com"},
                            }
                        ],
                    }
                )
            }
        return {}


def _new_ec2_with_rdp(  # noqa: PLR0913 # too many parameters, but it's more readable to specify them as arguments in the tests than pack them into a config object, they are keyword args anyways with a bunch of default values
    *,
    name: str = "test-instance",
    central_networking_subnet_name: str = "test-subnet",
    instance_type: str = "t3.micro",
    image_id: str = "ami-12345678",
    security_group_config: NewSecurityGroupConfig | ExistingSecurityGroupConfig | None = None,
    user_data: pulumi.Output[str] | None = None,
    additional_instance_tags: list[TagArgs] | None = None,
) -> Ec2WithRdp:
    if security_group_config is None:
        security_group_config = NewSecurityGroupConfig(central_networking_vpc_name="test-vpc")
    with (
        mock.patch("lab_auto_pulumi.ec2.common_tags_native", return_value=[]),
        mock.patch(
            "lab_auto_pulumi.ec2.get_org_managed_ssm_param_value",
            side_effect=_ssm_side_effect,
        ),
    ):
        return Ec2WithRdp(
            name=name,
            central_networking_subnet_name=central_networking_subnet_name,
            instance_type=instance_type,
            image_id=image_id,
            security_group_config=security_group_config,
            user_data=user_data,
            additional_instance_tags=additional_instance_tags,
        )


def _ssm_side_effect(param: str) -> str:
    return f"mock-{param.rsplit('/', maxsplit=1)[-1]}"


@pytest.fixture(autouse=True)
def ec2_mocks() -> Ec2Mocks:
    mocks = Ec2Mocks()
    pulumi.runtime.set_mocks(mocks, project="test-project", stack="test-stack")
    return mocks


class TestNewSecurityGroupConfig:
    @_pulumi_test
    def test_When_new_sg_config__Then_instance_has_correct_instance_type(self) -> pulumi.Output[None]:
        component = _new_ec2_with_rdp(instance_type="t3.micro")

        def check(instance_type: str | None) -> None:
            assert instance_type == "t3.micro"

        return component.instance.instance_type.apply(check)

    @_pulumi_test
    def test_When_new_sg_config__Then_instance_has_correct_image_id_and_subnet(self) -> pulumi.Output[None]:
        component = _new_ec2_with_rdp(
            image_id="ami-87654321",
            central_networking_subnet_name="my-subnet",
            instance_type="t3.large",
        )

        def check(args: list[Any]) -> None:
            image_id, subnet_id = args
            assert image_id == "ami-87654321"
            assert subnet_id == "mock-id", f"Expected 'mock-id' but got {subnet_id!r}"

        return pulumi.Output.all(
            component.instance.image_id,
            component.instance.subnet_id,
        ).apply(check)

    @_pulumi_test
    def test_When_new_sg_config__Then_security_group_created_with_vpc_id_from_ssm(self) -> pulumi.Output[None]:
        component = _new_ec2_with_rdp(
            security_group_config=NewSecurityGroupConfig(central_networking_vpc_name="test-vpc")
        )

        def check(vpc_id: str | None) -> None:
            assert vpc_id == "mock-id", f"Expected 'mock-id' but got {vpc_id!r}"

        return component.security_group.vpc_id.apply(check)

    @_pulumi_test
    def test_When_new_sg_with_ingress_rule__Then_ingress_resource_created(
        self, ec2_mocks: Ec2Mocks
    ) -> pulumi.Output[None]:
        component = _new_ec2_with_rdp(
            security_group_config=NewSecurityGroupConfig(
                central_networking_vpc_name="test-vpc",
                ingress_rules=[
                    ec2.SecurityGroupIngressArgs(
                        description="Allow RDP",
                        ip_protocol="tcp",
                        from_port=3389,
                        to_port=3389,
                    )
                ],
            )
        )

        def check(_: str) -> None:
            ingress = [r for r in ec2_mocks.created_resources if r.typ == "aws-native:ec2:SecurityGroupIngress"]
            assert [r.inputs.get("ipProtocol") for r in ingress] == ["tcp"]  # type: ignore[reportUnknownMemberType] # Pulumi SDK types inputs as dict[Unknown, Unknown]
            assert [r.inputs.get("fromPort") for r in ingress] == [3389]  # type: ignore[reportUnknownMemberType]
            assert [r.inputs.get("toPort") for r in ingress] == [3389]  # type: ignore[reportUnknownMemberType]

        return component.instance.id.apply(check)

    @_pulumi_test
    def test_When_new_sg_config__Then_egress_rule_always_created(self) -> pulumi.Output[None]:
        mocks = Ec2Mocks()
        pulumi.runtime.set_mocks(mocks, project="test-project", stack="test-stack")

        component = _new_ec2_with_rdp()

        def check(_: str) -> None:
            egress = [r for r in mocks.created_resources if r.typ == "aws-native:ec2:SecurityGroupEgress"]
            assert len(egress) == 1
            assert egress[0].inputs.get("ipProtocol") == "-1"  # type: ignore[reportUnknownMemberType] # Pulumi SDK types inputs as dict[Unknown, Unknown]
            assert egress[0].inputs.get("cidrIp") == "0.0.0.0/0"  # type: ignore[reportUnknownMemberType]

        return component.instance.id.apply(check)

    @_pulumi_test
    def test_When_ingress_rule_has_no_description__Then_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="must have a description"):
            _ = _new_ec2_with_rdp(
                security_group_config=NewSecurityGroupConfig(
                    central_networking_vpc_name="test-vpc",
                    ingress_rules=[
                        ec2.SecurityGroupIngressArgs(
                            description="",
                            ip_protocol="tcp",
                            from_port=3389,
                            to_port=3389,
                        )
                    ],
                )
            )


class TestExistingSecurityGroup:
    @_pulumi_test
    def test_When_existing_sg_config__Then_no_new_security_group_resource_created(self) -> pulumi.Output[None]:
        mocks = Ec2Mocks()
        pulumi.runtime.set_mocks(mocks, project="test-project", stack="test-stack")

        component = _new_ec2_with_rdp(
            security_group_config=ExistingSecurityGroupConfig(
                security_group_id=pulumi.Output.from_input("sg-existing-123")
            )
        )

        def check(_: str) -> None:
            # ec2.SecurityGroup.get() is a ReadResource, which flows through new_resource in the mock
            # with resource_id set to the ID being read. Assert we read the right one and never created a new one.
            read_sgs = [r for r in mocks.created_resources if r.typ == "aws-native:ec2:SecurityGroup" and r.resource_id]
            new_sgs = [
                r for r in mocks.created_resources if r.typ == "aws-native:ec2:SecurityGroup" and not r.resource_id
            ]
            assert [r.resource_id for r in read_sgs] == ["sg-existing-123"]
            assert new_sgs == [], f"Expected no new SecurityGroup resources but got {new_sgs}"

        return component.instance.id.apply(check)

    @_pulumi_test
    def test_When_existing_sg_config__Then_instance_uses_provided_sg_id(self) -> pulumi.Output[None]:

        component = _new_ec2_with_rdp(
            security_group_config=ExistingSecurityGroupConfig(
                security_group_id=pulumi.Output.from_input("sg-existing-123")
            )
        )

        def check(sg_ids: Sequence[Any] | None) -> None:
            assert sg_ids is not None, "Expected sg_ids to be not None"
            assert "sg-existing-123" in sg_ids, f"Expected 'sg-existing-123' in {sg_ids}"

        return component.instance.security_group_ids.apply(check)


class TestUserData:
    @_pulumi_test
    def test_When_user_data_provided__Then_instance_user_data_is_base64_encoded(self) -> pulumi.Output[None]:

        raw = "write-me-a-script"
        component = _new_ec2_with_rdp(user_data=pulumi.Output.from_input(raw))

        def check(encoded: str | None) -> None:
            expected = base64.b64encode(raw.encode()).decode()
            assert encoded == expected, f"Expected {expected!r} but got {encoded!r}"

        return component.instance.user_data.apply(check)

    @_pulumi_test
    def test_When_no_user_data__Then_instance_user_data_is_none(self) -> pulumi.Output[None]:

        component = _new_ec2_with_rdp(user_data=None)

        def check(user_data: str | None) -> None:
            assert user_data is None, f"Expected None but got {user_data!r}"

        return component.instance.user_data.apply(check)


@_pulumi_test
def test_When_additional_instance_tags_provided__Then_tags_appear_on_instance() -> pulumi.Output[None]:
    component = _new_ec2_with_rdp(
        additional_instance_tags=[
            TagArgs(key="env", value="testing"),
            TagArgs(key="owner", value="automation"),
        ]
    )

    def check(tags: Sequence[Any] | None) -> None:
        assert tags is not None, "Expected tags to be not None"
        tag_map: dict[str, str] = {t["key"]: t["value"] for t in tags}
        assert tag_map.get("env") == "testing", f"Missing or wrong 'env' tag in {tag_map}"
        assert tag_map.get("owner") == "automation", f"Missing or wrong 'owner' tag in {tag_map}"

    return component.instance.tags.apply(check)


@_pulumi_test
def test_When_component_created__Then_instance_role_has_ssm_managed_policy() -> pulumi.Output[None]:
    component = _new_ec2_with_rdp()

    def check(arns: Sequence[str] | None) -> None:
        assert arns is not None, "Expected arns to be not None"
        expected = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
        assert expected in arns, f"Expected SSM policy in {arns}"

    return component.instance_role.managed_policy_arns.apply(check)


@_pulumi_test
def test_When_component_created__Then_instance_role_trust_policy_allows_ec2() -> pulumi.Output[None]:
    component = _new_ec2_with_rdp()

    def check(policy_json: str) -> None:
        policy = json.loads(policy_json)
        services: str | list[str] = policy["Statement"][0]["Principal"]["Service"]
        if isinstance(services, str):
            services = [services]
        assert "ec2.amazonaws.com" in services, f"Expected ec2.amazonaws.com in trust policy but got {services}"

    return component.instance_role.assume_role_policy_document.apply(check)
