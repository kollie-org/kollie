from unittest.mock import Mock

import pytest

from kollie.cluster.image_policy_spec import LatestTimestampImagePolicySpec


@pytest.mark.parametrize(
    "branch,image_prefix",
    [
        ("main", "main"),
        ("develop", "develop"),
        ("feature/foo$!@%!@^bar", "feature-foo-bar"),
        ("ILIKE🚆TRAINS", "ILIKE-TRAINS"),
        ("numbers€are123FINE", "numbers-are123FINE"),
    ],
)
def test_for_image_tag_prefix_with_different_branches(branch, image_prefix):
    app_template = Mock()
    image_repository_ref = Mock()
    image_repository_ref.name = "test_repo"
    image_repository_ref.namespace = "test_namespace"

    app_template.image_repository_ref = image_repository_ref

    policy_spec = LatestTimestampImagePolicySpec.for_image_tag_prefix(app_template, branch)

    assert isinstance(policy_spec, LatestTimestampImagePolicySpec)

    assert policy_spec.imageRepositoryRef.name == "test_repo"
    assert policy_spec.imageRepositoryRef.namespace == "test_namespace"
    assert policy_spec.filterTags.pattern == f"^{image_prefix}-[a-fA-F0-9]+-(?P<ts>.*)"
    assert policy_spec.filterTags.extract == "$ts"
    assert policy_spec.policy == {"numerical": {"order": "asc"}}
