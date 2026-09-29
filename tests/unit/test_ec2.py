import base64
import json
import random
import uuid
from collections.abc import Callable
from collections.abc import Sequence
from enum import Enum
from enum import auto
from typing import Any
from unittest import mock

import pulumi
import pulumi.runtime
import pytest
from faker import Faker
from pulumi_aws.iam import GetPolicyDocumentStatementArgsDict
from pulumi_aws_native import TagArgs
from pulumi_aws_native import ec2
from pulumi_aws_native.outputs import Tag
from pydantic import TypeAdapter

from lab_auto_pulumi import ec2 as lab_auto_ec2_module
from lab_auto_pulumi.ec2 import Ec2WithRdp
from lab_auto_pulumi.ec2 import ExistingSecurityGroupConfig
from lab_auto_pulumi.ec2 import NewSecurityGroupConfig

_pulumi_test = pulumi.runtime.test  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType] # pulumi.runtime.test is partially typed in the Pulumi SDK; alias avoids repeating the ignore on every test

_EC2_INSTANCE_TYPES = ["t3.micro", "t3.large", "m5.xlarge", "c5.2xlarge"]
_AWS_REGIONS = ["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-2"]
_AWS_PARTITIONS = ["aws", "aws-cn", "aws-us-gov"]
_POLICY_STATEMENTS_ADAPTER = TypeAdapter(list[GetPolicyDocumentStatementArgsDict])
_IGNORABLE_INSTANCE_PROPERTIES = ["imageId", "tags", "userData"]


class _Unset(Enum):
    TOKEN = auto()


class Ec2Mocks(pulumi.runtime.Mocks):
    def __init__(self) -> None:
        super().__init__()
        self.created_resources: list[pulumi.runtime.MockResourceArgs] = []
        self.captured_calls: list[pulumi.runtime.MockCallArgs] = []
        self.region = random.choice(_AWS_REGIONS)
        self.partition = random.choice(_AWS_PARTITIONS)
        self.role_names: dict[str, str] = {}

    def new_resource(self, args: pulumi.runtime.MockResourceArgs) -> tuple[str, dict[str, Any]]:  # type: ignore[override] # pyright infers Optional[str] for id but str is always safe here
        self.created_resources.append(args)
        resource_id = args.resource_id if bool(args.resource_id) else f"{args.name}-id"
        if args.typ == "aws-native:iam:Role":
            self.role_names[args.name] = f"role-{uuid.uuid4().hex}"
            return (resource_id, {**args.inputs, "roleName": self.role_names[args.name]})  # pyright: ignore[reportUnknownMemberType] # Pulumi SDK types inputs as dict[Unknown, Unknown]
        return (resource_id, args.inputs)  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType] # Pulumi SDK types inputs as dict[Unknown, Unknown]

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
        if args.token == "aws-native:index:getRegion":  # noqa:S105 # definitely not a password
            return {"region": self.region}
        if args.token == "aws-native:index:getPartition":  # noqa:S105 # definitely not a password
            return {"partition": self.partition}
        return {}


def _new_ec2_with_rdp(  # noqa: PLR0913 # too many parameters, but it's more readable to specify them as arguments in the tests than pack them into a config object, they are keyword args anyways with a bunch of default values
    *,
    name: str | _Unset = _Unset.TOKEN,
    central_networking_subnet_name: str | _Unset = _Unset.TOKEN,
    instance_type: str | _Unset = _Unset.TOKEN,
    image_id: str | _Unset = _Unset.TOKEN,
    security_group_config: NewSecurityGroupConfig | ExistingSecurityGroupConfig | _Unset = _Unset.TOKEN,
    user_data: pulumi.Output[str] | _Unset | None = _Unset.TOKEN,
    additional_instance_tags: list[TagArgs] | _Unset | None = _Unset.TOKEN,
    instance_ignore_changes: list[str] | _Unset | None = _Unset.TOKEN,
    enable_dcv: bool | _Unset = _Unset.TOKEN,
    parent: pulumi.Resource | _Unset | None = _Unset.TOKEN,
) -> Ec2WithRdp:
    faker = Faker()
    with (
        mock.patch.object(lab_auto_ec2_module, lab_auto_ec2_module.common_tags_native.__name__, return_value=[]),
        mock.patch.object(
            lab_auto_ec2_module,
            lab_auto_ec2_module.get_org_managed_ssm_param_value.__name__,
            side_effect=_ssm_side_effect,
        ),
    ):
        return Ec2WithRdp(
            name=_or_random(name, faker.slug),
            central_networking_subnet_name=_or_random(central_networking_subnet_name, faker.slug),
            instance_type=_or_random(instance_type, lambda: random.choice(_EC2_INSTANCE_TYPES)),
            image_id=_or_random(image_id, lambda: f"ami-{faker.hexify('^^^^^^^^')}"),
            security_group_config=_or_random(security_group_config, lambda: _random_security_group_config(faker)),
            user_data=_or_random(user_data, lambda: random.choice([None, pulumi.Output.from_input(faker.sentence())])),
            additional_instance_tags=_or_random(additional_instance_tags, lambda: _random_tags(faker)),
            instance_ignore_changes=_or_random(
                instance_ignore_changes,
                lambda: random.choice([None, random.sample(_IGNORABLE_INSTANCE_PROPERTIES, k=random.randint(0, 2))]),
            ),
            enable_dcv=_or_random(enable_dcv, lambda: random.choice([True, False])),
            parent=_or_random(parent, lambda: _random_parent(faker)),
        )


def _or_random[T](value: T | _Unset, factory: Callable[[], T]) -> T:
    if isinstance(value, _Unset):
        return factory()
    return value


def _random_tags(faker: Faker) -> list[TagArgs] | None:
    return random.choice(
        [None, [TagArgs(key=faker.unique.word(), value=faker.word()) for _ in range(random.randint(0, 3))]]
    )


def _random_parent(faker: Faker) -> pulumi.Resource | None:
    if random.choice([True, False]):
        return pulumi.ComponentResource("test:index:Parent", faker.slug())
    return None


def _random_security_group_config(faker: Faker) -> NewSecurityGroupConfig | ExistingSecurityGroupConfig:
    ingress_port = random.randint(1, 65535)
    return random.choice(
        [
            NewSecurityGroupConfig(central_networking_vpc_name=faker.slug()),
            NewSecurityGroupConfig(
                central_networking_vpc_name=faker.slug(),
                ingress_rules=[
                    ec2.SecurityGroupIngressArgs(
                        description=faker.sentence(),
                        ip_protocol=random.choice(["tcp", "udp"]),
                        from_port=ingress_port,
                        to_port=ingress_port,
                    )
                ],
            ),
            ExistingSecurityGroupConfig(security_group_id=pulumi.Output.from_input(f"sg-{faker.hexify('^^^^^^^^')}")),
        ]
    )


def _ssm_side_effect(param: str) -> str:
    return f"mock-{param.rsplit('/', maxsplit=1)[-1]}"


def _expected_ssm_managed_instance_core_arn(mocks: Ec2Mocks) -> str:
    return f"arn:{mocks.partition}:iam::aws:policy/AmazonSSMManagedInstanceCore"


def _policy_document_statements_with_actions(
    mocks: Ec2Mocks, *, actions: list[str]
) -> list[GetPolicyDocumentStatementArgsDict]:
    return [
        statement
        for call in mocks.captured_calls
        if call.token == "aws:iam/getPolicyDocument:getPolicyDocument"  # noqa:S105 # definitely not a password
        for statement in _POLICY_STATEMENTS_ADAPTER.validate_python(call.args["statements"])  # pyright: ignore[reportUnknownMemberType] # MockCallArgs.args is typed as bare dict in the Pulumi SDK
        if statement.get("actions") == actions
    ]


@pytest.fixture(autouse=True)
def ec2_mocks() -> Ec2Mocks:
    mocks = Ec2Mocks()
    pulumi.runtime.set_mocks(mocks, project="test-project", stack="test-stack")
    return mocks


class TestNewSecurityGroupConfig:
    @_pulumi_test
    def test_When_new_sg_config__Then_instance_has_correct_instance_type(self, faker: Faker) -> pulumi.Output[None]:
        instance_type = random.choice(_EC2_INSTANCE_TYPES)
        component = _new_ec2_with_rdp(
            instance_type=instance_type,
            security_group_config=NewSecurityGroupConfig(central_networking_vpc_name=faker.slug()),
        )

        def check(actual: str | None) -> None:
            assert actual == instance_type

        return component.instance.instance_type.apply(check)

    @_pulumi_test
    def test_When_new_sg_config__Then_instance_has_correct_image_id_and_subnet(
        self, faker: Faker
    ) -> pulumi.Output[None]:
        image_id = f"ami-{faker.hexify('^^^^^^^^')}"
        component = _new_ec2_with_rdp(
            image_id=image_id,
            central_networking_subnet_name=faker.slug(),
            security_group_config=NewSecurityGroupConfig(central_networking_vpc_name=faker.slug()),
        )

        def check(args: list[object]) -> None:
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
            assert [r.inputs.get("ipProtocol") for r in ingress] == ["tcp"]  # pyright: ignore[reportUnknownMemberType] # Pulumi SDK types inputs as dict[Unknown, Unknown]
            assert [r.inputs.get("fromPort") for r in ingress] == [3389]  # pyright: ignore[reportUnknownMemberType]
            assert [r.inputs.get("toPort") for r in ingress] == [3389]  # pyright: ignore[reportUnknownMemberType]

        return component.instance.id.apply(check)

    @_pulumi_test
    def test_When_new_sg_config__Then_egress_rule_always_created(
        self, ec2_mocks: Ec2Mocks, faker: Faker
    ) -> pulumi.Output[None]:
        component = _new_ec2_with_rdp(
            security_group_config=NewSecurityGroupConfig(central_networking_vpc_name=faker.slug())
        )

        def check(_: str) -> None:
            egress = [r for r in ec2_mocks.created_resources if r.typ == "aws-native:ec2:SecurityGroupEgress"]
            assert len(egress) == 1
            assert egress[0].inputs.get("ipProtocol") == "-1"  # pyright: ignore[reportUnknownMemberType] # Pulumi SDK types inputs as dict[Unknown, Unknown]
            assert egress[0].inputs.get("cidrIp") == "0.0.0.0/0"  # pyright: ignore[reportUnknownMemberType]

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
        sg_id = f"sg-{faker.hexify('^^^^^^^^')}"
        component = _new_ec2_with_rdp(
            security_group_config=ExistingSecurityGroupConfig(security_group_id=pulumi.Output.from_input(sg_id))
        )

        def check(_: str) -> None:
            # ec2.SecurityGroup.get() is a ReadResource, which flows through new_resource in the mock
            # with resource_id set to the ID being read. Assert we read the right one and never created a new one.
            read_sgs = [
                r
                for r in ec2_mocks.created_resources
                if r.typ == "aws-native:ec2:SecurityGroup" and bool(r.resource_id)
            ]
            new_sgs = [
                r
                for r in ec2_mocks.created_resources
                if r.typ == "aws-native:ec2:SecurityGroup" and not bool(r.resource_id)
            ]
            assert [r.resource_id for r in read_sgs] == [sg_id]
            assert new_sgs == [], f"Expected no new SecurityGroup resources but got {new_sgs}"

        return component.instance.id.apply(check)

    @_pulumi_test
    def test_When_existing_sg_config__Then_instance_uses_provided_sg_id(self, faker: Faker) -> pulumi.Output[None]:
        sg_id = f"sg-{faker.hexify('^^^^^^^^')}"
        component = _new_ec2_with_rdp(
            security_group_config=ExistingSecurityGroupConfig(security_group_id=pulumi.Output.from_input(sg_id))
        )

        def check(sg_ids: Sequence[object] | None) -> None:
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
    key_one = faker.unique.word()
    value_one = faker.word()
    key_two = faker.unique.word()
    value_two = faker.word()
    component = _new_ec2_with_rdp(
        additional_instance_tags=[
            TagArgs(key=key_one, value=value_one),
            TagArgs(key=key_two, value=value_two),
        ]
    )

    def check(tags: Sequence[Tag] | None) -> None:
        assert tags is not None, "Expected tags to be not None"
        tag_map = {t.key: t.value for t in tags}
        assert tag_map.get(key_one) == value_one, f"Missing or wrong {key_one!r} tag in {tag_map}"
        assert tag_map.get(key_two) == value_two, f"Missing or wrong {key_two!r} tag in {tag_map}"

    return component.instance.tags.apply(check)


@_pulumi_test
def test_When_component_created__Then_instance_role_has_ssm_managed_policy_in_resolved_partition(
    ec2_mocks: Ec2Mocks,
) -> pulumi.Output[None]:
    component = _new_ec2_with_rdp()

    def check(arns: Sequence[str] | None) -> None:
        assert arns == [_expected_ssm_managed_instance_core_arn(ec2_mocks)]

    return component.instance_role.managed_policy_arns.apply(check)


@_pulumi_test
def test_When_component_created__Then_instance_role_trust_policy_allows_ec2(
    ec2_mocks: Ec2Mocks,
) -> pulumi.Output[None]:
    component = _new_ec2_with_rdp()

    def check(_: str) -> None:
        trust_statements = _policy_document_statements_with_actions(ec2_mocks, actions=["sts:AssumeRole"])
        assert len(trust_statements) == 1
        stmt = trust_statements[0]
        assert stmt.get("effect") == "Allow"
        assert stmt.get("actions") == ["sts:AssumeRole"]
        principals = stmt.get("principals")
        assert principals is not None
        assert len(principals) == 1
        assert principals[0]["type"] == "Service"
        assert principals[0]["identifiers"] == ["ec2.amazonaws.com"]

    return component.instance_role.assume_role_policy_document.apply(check)


def test_When_enable_dcv_true__Then_dcv_license_policy_attached_to_instance_role_as_separate_role_policy(
    ec2_mocks: Ec2Mocks,
) -> None:
    @_pulumi_test
    def create_component() -> None:
        _ = _new_ec2_with_rdp(enable_dcv=True)

    create_component()

    roles = [r for r in ec2_mocks.created_resources if r.typ == "aws-native:iam:Role"]
    role_policies = [r for r in ec2_mocks.created_resources if r.typ == "aws:iam/rolePolicy:RolePolicy"]
    dcv_statements = _policy_document_statements_with_actions(ec2_mocks, actions=["s3:GetObject"])

    assert len(roles) == 1
    assert "policies" not in roles[0].inputs  # pyright: ignore[reportUnknownMemberType] # Pulumi SDK types inputs as dict[Unknown, Unknown]
    assert len(role_policies) == 1
    assert role_policies[0].inputs["role"] == ec2_mocks.role_names[roles[0].name]  # pyright: ignore[reportUnknownMemberType]
    assert dcv_statements == [
        {
            "effect": "Allow",
            "actions": ["s3:GetObject"],
            "resources": [f"arn:{ec2_mocks.partition}:s3:::dcv-license.{ec2_mocks.region}/*"],
        }
    ]


def test_When_enable_dcv_false__Then_instance_role_has_no_dcv_policy(ec2_mocks: Ec2Mocks) -> None:
    @_pulumi_test
    def create_component() -> None:
        _ = _new_ec2_with_rdp(enable_dcv=False)

    create_component()

    roles = [r for r in ec2_mocks.created_resources if r.typ == "aws-native:iam:Role"]
    role_policies = [r for r in ec2_mocks.created_resources if r.typ == "aws:iam/rolePolicy:RolePolicy"]

    assert len(roles) == 1
    assert roles[0].inputs["managedPolicyArns"] == [_expected_ssm_managed_instance_core_arn(ec2_mocks)]  # pyright: ignore[reportUnknownMemberType] # Pulumi SDK types inputs as dict[Unknown, Unknown]
    assert "policies" not in roles[0].inputs  # pyright: ignore[reportUnknownMemberType]
    assert role_policies == []
    assert _policy_document_statements_with_actions(ec2_mocks, actions=["s3:GetObject"]) == []
