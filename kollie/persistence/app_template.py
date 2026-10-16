from dataclasses import dataclass

from kollie.cluster.constants import DEFAULT_FLUX_REPOSITORY


@dataclass
class ImageRepositoryRef:
    """
    Reference to a deployed ImageRepository resource in a namespace.
    This ImageRepository reference is used as the basis for ImagePolicies
    created for monitoring for image pushes
    """

    name: str
    namespace: str


@dataclass
class AppTemplate:
    """Describes a template for an application that Kollie can deploy."""

    app_name: str
    label: str
    git_repository_name: str
    git_repository_path: str
    default_image_tag_prefix: str
    image_repository_ref: ImageRepositoryRef

    @classmethod
    def from_dict(cls, data: dict) -> "AppTemplate":
        image_repository_ref = ImageRepositoryRef(
            name=data["image_repository_ref"]["name"],
            namespace=data["image_repository_ref"]["namespace"],
        )

        return cls(
            app_name=data["app_name"],
            label=data["label"],
            git_repository_name=data.get("git_repository_name", DEFAULT_FLUX_REPOSITORY or ""),
            git_repository_path=data["git_repository_path"],
            image_repository_ref=image_repository_ref,
            default_image_tag_prefix=data["default_image_tag_prefix"],
        )
