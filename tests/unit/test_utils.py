from lab_auto_pulumi import create_resource_name_safe_str


def test_When_create_resource_name_safe_str__Then_invalid_characters_converted():
    actual = create_resource_name_safe_str("a:b c(d)e'f" + '"g/h=i' + r"\j" + ":k")

    assert actual == "a-b-c-d-e-f-g-h-i-j-k"
