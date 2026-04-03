import base64
import json
import random
from collections.abc import Sequence
from typing import Any
from unittest import mock

import pulumi
import pulumi.runtime
import pytest
from faker import Faker
from pulumi_aws_native import TagArgs
from pulumi_aws_native import ec2

from lab_auto_pulumi import ec2 as lab_auto_ec2_module
from lab_auto_pulumi.ec2 import Ec2WithRdp
from lab_auto_pulumi.ec2 import ExistingSecurityGroupConfig
from lab_auto_pulumi.ec2 import NewSecurityGroupConfig

_pulumi_test = pulumi.runtime.test  # type: ignore[reportUnknownMemberType] # pulumi.runtime.test is partially typed in the Pulumi SDK; alias avoids repeating the ignore on every test

_EC2_INSTANCE_TYPES = ["t3.micro", "t3.large", "m5.xlarge", "c5.2xlarge"]


class Ec2Mocks(pulumi.runtime.Mocks):
    def __init__(self) -> None:
        super().__init__()
        self.created_resources: list[pulumi.runtime.MockResourceArgs] = []
        self.captured_calls: list[pulumi.runtime.MockCallArgs] = []

    def new_resource(self, args: pulumi.runtime.MockResourceArgs) -> tuple[str, dict[str, Any]]:  # type: ignore[override] # pyright infers Optional[str] for id but str is always safe here
        self.created_resources.append(args)
        resource_id = args.resource_id or f"{args.name}-id"
        return (resource_id, args.inputs)  # type: ignore[return-value] # Pulumi SDK types inputs as dict[Unknown, Unknown]

    def call(self, args: pulumi.runtime.MockCallArgs) -> dict[str, Any]:  # type: ignore[override] # pyright infers tuple[dict, Optional[list]] but plain dict is accepted
        self.captured_calls.append(args)
        if args.token == "aws:iam/getPolicyDocument:getPolicyDocument":  # noqa:S105 # definitely not a password
            return {
                "json": json.dumps(
                    {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Effect": "Allow",
                                "Action": "sts:AssumeRole",
                                "Principal": {"Service": Faker().slug() + ".amazonaws.com"},
                            }
                        ],
                    }
                )
            }
        return {}


def _new_ec2_with_rdp(  # noqa: PLR0913 # too many parameters, but it's more readable to specify them as arguments in the tests than pack them into a config object, they are keyword args anyways with a bunch of default values
    *,
    name: str | None = None,
    central_networking_subnet_name: str | None = None,
    instance_type: str | None = None,
    image_id: str | None = None,
    security_group_config: NewSecurityGroupConfig | ExistingSecurityGroupConfig | None = None,
    user_data: pulumi.Output[str] | None = None,
    additional_instance_tags: list[TagArgs] | None = None,
) -> Ec2WithRdp:
    _faker = Faker()
    if name is None:
        name = _faker.slug()
    if central_networking_subnet_name is None:
        central_networking_subnet_name = _faker.slug()
    if instance_type is None:
        instance_type = random.choice(_EC2_INSTANCE_TYPES)
    if image_id is None:
        image_id = f"ami-{_faker.hexify('????????')}"
    if security_group_config is None:
        security_group_config = NewSecurityGroupConfig(central_networking_vpc_name=_faker.slug())
    with (
        mock.patch.object(lab_auto_ec2_module, lab_auto_ec2_module.common_tags_native.__name__, return_value=[]),
        mock.patch.object(
            lab_auto_ec2_module,
            lab_auto_ec2_module.get_org_managed_ssm_param_value.__name__,
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
        instance_type = random.choice(_EC2_INSTANCE_TYPES)
        component = _new_ec2_with_rdp(instance_type=instance_type)

        def check(actual: str | None) -> None:
            assert actual == instance_type

        return component.instance.instance_type.apply(check)

    @_pulumi_test
    def test_When_new_sg_config__Then_instance_has_correct_image_id_and_subnet(
        self, faker: Faker
    ) -> pulumi.Output[None]:
        image_id = f"ami-{faker.hexify('????????')}"
        component = _new_ec2_with_rdp(
            image_id=image_id,
            central_networking_subnet_name=faker.slug(),
            instance_type=random.choice(_EC2_INSTANCE_TYPES),
        )

        def check(args: list[Any]) -> None:
            actual_image_id, actual_subnet_id = args
            assert actual_image_id == image_id
            assert actual_subnet_id == "mock-id", f"Expected 'mock-id' but got {actual_subnet_id!r}"

        return pulumi.Output.all(
            component.instance.image_id,
            component.instance.subnet_id,
        ).apply(check)

    @_pulumi_test
    def test_When_new_sg_config__Then_security_group_created_with_vpc_id_from_ssm(
        self, faker: Faker
    ) -> pulumi.Output[None]:
        component = _new_ec2_with_rdp(
            security_group_config=NewSecurityGroupConfig(central_networking_vpc_name=faker.slug())
        )

        def check(vpc_id: str | None) -> None:
            assert vpc_id == "mock-id", f"Expected 'mock-id' but got {vpc_id!r}"

        return component.security_group.vpc_id.apply(check)

    @_pulumi_test
    def test_When_new_sg_with_ingress_rule__Then_ingress_resource_created(
        self, ec2_mocks: Ec2Mocks, faker: Faker
    ) -> pulumi.Output[None]:
        component = _new_ec2_with_rdp(
            security_group_config=NewSecurityGroupConfig(
                central_networking_vpc_name=faker.slug(),
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
    def test_When_new_sg_config__Then_egress_rule_always_created(self, ec2_mocks: Ec2Mocks) -> pulumi.Output[None]:
        component = _new_ec2_with_rdp()

        def check(_: str) -> None:
            egress = [r for r in ec2_mocks.created_resources if r.typ == "aws-native:ec2:SecurityGroupEgress"]
            assert len(egress) == 1
            assert egress[0].inputs.get("ipProtocol") == "-1"  # type: ignore[reportUnknownMemberType] # Pulumi SDK types inputs as dict[Unknown, Unknown]
            assert egress[0].inputs.get("cidrIp") == "0.0.0.0/0"  # type: ignore[reportUnknownMemberType]

        return component.instance.id.apply(check)

    @_pulumi_test
    def test_When_ingress_rule_has_no_description__Then_raises_value_error(self, faker: Faker) -> None:
        with pytest.raises(ValueError, match="must have a description"):
            _ = _new_ec2_with_rdp(
                security_group_config=NewSecurityGroupConfig(
                    central_networking_vpc_name=faker.slug(),
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
    def test_When_existing_sg_config__Then_no_new_security_group_resource_created(
        self, faker: Faker, ec2_mocks: Ec2Mocks
    ) -> pulumi.Output[None]:
        sg_id = f"sg-{faker.hexify('????????')}"
        component = _new_ec2_with_rdp(
            security_group_config=ExistingSecurityGroupConfig(security_group_id=pulumi.Output.from_input(sg_id))
        )

        def check(_: str) -> None:
            # ec2.SecurityGroup.get() is a ReadResource, which flows through new_resource in the mock
            # with resource_id set to the ID being read. Assert we read the right one and never created a new one.
            read_sgs = [
                r for r in ec2_mocks.created_resources if r.typ == "aws-native:ec2:SecurityGroup" and r.resource_id
            ]
            new_sgs = [
                r for r in ec2_mocks.created_resources if r.typ == "aws-native:ec2:SecurityGroup" and not r.resource_id
            ]
            assert [r.resource_id for r in read_sgs] == [sg_id]
            assert new_sgs == [], f"Expected no new SecurityGroup resources but got {new_sgs}"

        return component.instance.id.apply(check)

    @_pulumi_test
    def test_When_existing_sg_config__Then_instance_uses_provided_sg_id(self, faker: Faker) -> pulumi.Output[None]:
        sg_id = f"sg-{faker.hexify('????????')}"
        component = _new_ec2_with_rdp(
            security_group_config=ExistingSecurityGroupConfig(security_group_id=pulumi.Output.from_input(sg_id))
        )

        def check(sg_ids: Sequence[Any] | None) -> None:
            assert sg_ids is not None, "Expected sg_ids to be not None"
            assert sg_id in sg_ids, f"Expected {sg_id!r} in {sg_ids}"

        return component.instance.security_group_ids.apply(check)


class TestUserData:
    @_pulumi_test
    def test_When_user_data_provided__Then_instance_user_data_is_base64_encoded(
        self, faker: Faker
    ) -> pulumi.Output[None]:

        raw_user_data_script = faker.sentence()
        component = _new_ec2_with_rdp(user_data=pulumi.Output.from_input(raw_user_data_script))

        def check(encoded: str | None) -> None:
            expected = base64.b64encode(raw_user_data_script.encode()).decode()
            assert encoded == expected, f"Expected {expected!r} but got {encoded!r}"

        return component.instance.user_data.apply(check)

    @_pulumi_test
    def test_When_no_user_data__Then_instance_user_data_is_none(self) -> pulumi.Output[None]:
        component = _new_ec2_with_rdp(user_data=None)

        def check(user_data: str | None) -> None:
            assert user_data is None, f"Expected None but got {user_data!r}"

        return component.instance.user_data.apply(check)


@_pulumi_test
def test_When_additional_instance_tags_provided__Then_tags_appear_on_instance(faker: Faker) -> pulumi.Output[None]:
    key_one = faker.word()
    value_one = faker.word()
    key_two = faker.word()
    value_two = faker.word()
    component = _new_ec2_with_rdp(
        additional_instance_tags=[
            TagArgs(key=key_one, value=value_one),
            TagArgs(key=key_two, value=value_two),
        ]
    )

    def check(tags: Sequence[Any] | None) -> None:
        assert tags is not None, "Expected tags to be not None"
        tag_map: dict[str, str] = {t["key"]: t["value"] for t in tags}
        assert tag_map.get(key_one) == value_one, f"Missing or wrong {key_one!r} tag in {tag_map}"
        assert tag_map.get(key_two) == value_two, f"Missing or wrong {key_two!r} tag in {tag_map}"

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
def test_When_component_created__Then_instance_role_trust_policy_allows_ec2(
    ec2_mocks: Ec2Mocks,
) -> pulumi.Output[None]:
    component = _new_ec2_with_rdp()

    def check(_: str) -> None:
        policy_calls = [c for c in ec2_mocks.captured_calls if c.token == "aws:iam/getPolicyDocument:getPolicyDocument"]  # noqa:S105 # definitely not a password
        assert len(policy_calls) == 1
        call_args: dict[str, Any] = policy_calls[0].args  # type: ignore[reportUnknownMemberType] # MockCallArgs.args is typed as bare dict in the Pulumi SDK
        statements: list[dict[str, Any]] = call_args.get("statements", [])
        assert len(statements) == 1
        stmt = statements[0]
        assert stmt.get("effect") == "Allow"
        assert stmt.get("actions") == ["sts:AssumeRole"]
        principals: list[dict[str, Any]] = stmt.get("principals", [])
        assert len(principals) == 1
        assert principals[0].get("type") == "Service"
        assert principals[0].get("identifiers") == ["ec2.amazonaws.com"]

    return component.instance_role.assume_role_policy_document.apply(check)
