from typing import Any
from typing import cast
from typing import override

import pulumi
import pulumi.runtime


# Define mocks to simulate resource creation.
class MyMocks(pulumi.runtime.Mocks):
    @override
    def new_resource(self, args: pulumi.runtime.MockResourceArgs) -> tuple[str | None, dict[Any, Any]]:
        args.inputs = cast("dict[Any, Any]", args.inputs)  # pyright: ignore[reportUnknownMemberType] # the underlying library is not fully typed
        return (
            args.name + "_id",
            args.inputs,  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType] # the underlying library is not fully typed...and I'm not sure why the `cast` above isn't helping
        )

    @override
    def call(self, args: pulumi.runtime.MockCallArgs) -> tuple[dict[Any, Any], None | list[tuple[str, str]]]:
        return ({}, None)


# Set the mocks before creating any resources.
pulumi.runtime.set_mocks(MyMocks(), preview=False)

from lab_auto_pulumi import Ec2WithRdp  # noqa: E402,I001 # importing pulumi modules has to take place after mocks are set


def test_ec2():
    assert Ec2WithRdp is not True
