import re
from dataclasses import dataclass

from .interfaces import AppTemplate, ClusterObjectReference


@dataclass
class ImageFilter:
    """
    Value object for ImagePolicy.spec.filterTags
    See https://fluxcd.io/flux/components/image/imagepolicies/#filter-tags
    """

    pattern: str
    extract: str


@dataclass
class ImagePolicySpec:
    """
    Base class for ImagePolicy.spec
    See https://fluxcd.io/flux/components/image/imagepolicies/
    """

    imageRepositoryRef: ClusterObjectReference
    filterTags: ImageFilter
    policy: dict


class LatestTimestampImagePolicySpec(ImagePolicySpec):
    """
    This class provides a factory for generating a ImagePolicy.spec
    that takes the latest image tag using timestamp for images tagged
    in the pattern {branch}-{commit-hash}-{timestamp}

    i.e. the majority of use cases
    """

    @classmethod
    def for_image_tag_prefix(
        cls, app_template: AppTemplate, image_tag_prefix: str
    ) -> "LatestTimestampImagePolicySpec":
        """
        Creates an image policy spec for a given image tag prefix, to find the newest matching tag. It transforms the name
        of a branch into the container image tag prefix in the same way as the Docker metadata action:
        https://github.com/docker/metadata-action#image-name-and-tag-sanitization
        """
        image_prefix = re.sub(r"[^a-zA-Z0-9._-]+", "-", image_tag_prefix)

        return cls(
            imageRepositoryRef=app_template.image_repository_ref,
            filterTags=ImageFilter(
                pattern=f"^{image_prefix}-[a-fA-F0-9]+-(?P<ts>.*)", extract="$ts"
            ),
            policy={"numerical": {"order": "asc"}},
        )
