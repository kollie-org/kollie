import datetime
import json
from dataclasses import dataclass, field

from kubernetes.client.models.v1_ingress import V1Ingress


@dataclass
class KollieAppEvent:
    ready: bool | None = False
    type: str | None = None
    status_reason: str | None = None
    status_message: str | None = None

    @classmethod
    def from_condition(cls, condition):
        return cls(
            ready=condition["status"] == "True",
            type=condition["type"],
            status_reason=condition["reason"],
            status_message=condition["message"],
        )


@dataclass
class LeaseInfo:
    """
    Lease information for a KollieApp.
    This can house schedule information in the future.
    """

    lease_until: datetime.datetime

    @property
    def is_expired(self) -> bool:
        return datetime.datetime.now(datetime.UTC) > self.lease_until

    @property
    def time_left(self) -> datetime.timedelta:
        return self.lease_until - datetime.datetime.now(datetime.UTC)


@dataclass
class KollieApp:
    name: str
    env_name: str
    owner_email: str
    image_tag: str | None = None
    image_tag_prefix: str | None = None
    events: list[KollieAppEvent] = field(default_factory=list)
    lease_until: datetime.datetime | None = None
    urls: list[str] = field(default_factory=list)

    @property
    def status(self) -> KollieAppEvent:
        """
        Safe accessor for the most recent event.
        A KollieAppEvent object is synthesised if no events are present.
        """
        if self.events:
            return self.events[-1]

        return KollieAppEvent(
            ready=False,
            type="Unknown",
            status_reason="No events",
            status_message="No events have been recorded for this app.",
        )

    @property
    def lease_info(self) -> LeaseInfo | None:
        if self.lease_until:
            return LeaseInfo(lease_until=self.lease_until)

        return None

    @staticmethod
    def _build_events(conditions):
        """
        Build a list of KollieAppEvent objects from a list of conditions.

        Args:
            conditions (List[dict]): The list of conditions.

        Returns:
            List[KollieAppEvent]: The list of events.
        """
        events = []
        for condition in conditions:
            event = KollieAppEvent.from_condition(condition)
            events.append(event)
        return events

    @staticmethod
    def _build_urls(ingress):
        """
        Build a list of URLs from an ingress resource.

        Args:
            ingress (V1Ingress): The ingress resource.

        Returns:
            List[str]: The list of URLs.
        """
        url_limit = 10

        urls = []
        for rule in ingress.spec.rules:
            host = rule.host
            for path in rule.http.paths:
                url = f"https://{host}{path.path}"
                urls.append(url)

                if len(urls) >= url_limit:
                    break
        return urls

    @classmethod
    def from_resources(
        cls, kustomization: dict, ingress: V1Ingress | None
    ) -> "KollieApp":
        """
        Build a KollieApp object from a set of resources.

        Args:
            kustomization (dict): The kustomization resource.
            ingress (V1Ingress): The ingress resource.

        Returns:
            KollieApp: The app object.
        """
        post_build = kustomization["spec"]["postBuild"]["substitute"]
        image_tag = post_build.get("image_tag")

        labels = kustomization["metadata"]["labels"]
        app_name = labels["tails-app-name"]
        env_name = labels["tails-app-environment"]

        annotations = kustomization["metadata"]["annotations"]
        image_tag_prefix = annotations.get("tails.com/tracking-image-tag-prefix")
        # Here so environments made before the nomenclature change don't break
        if not image_tag_prefix:
            image_tag_prefix = annotations.get("tails.com/tracking-branch")
        owner_email = annotations.get("tails.com/owner")

        conditions = kustomization["status"].get("conditions", [])
        events = []
        urls = []

        if conditions:
            events = cls._build_events(conditions)

        try:
            lease_until = _datetime_from_str(post_build["downscaler_uptime"])
        except KeyError:
            lease_until = None
        except ValueError:
            lease_until = None

        if ingress:
            urls = cls._build_urls(ingress)

        return cls(
            name=app_name,
            env_name=env_name,
            owner_email=owner_email,
            image_tag=image_tag,
            image_tag_prefix=image_tag_prefix,
            lease_until=lease_until,
            events=events,
            urls=urls,
        )


@dataclass
class KollieEnvironment:
    name: str
    apps: list[KollieApp]
    owner_email: str
    flux_repository_branch: str | None
    created_on: datetime.datetime | None = None

    @classmethod
    def from_kustomizations(
        cls,
        env_name: str,
        kustomizations: list[dict],
        owner_email: str,
        flux_repository_branch: str | None
    ):
        apps = []

        for kustomization in kustomizations:
            app = KollieApp.from_resources(kustomization, ingress=None)
            apps.append(app)

        return cls(
            name=env_name,
            owner_email=owner_email,
            apps=apps,
            flux_repository_branch=flux_repository_branch
        )

    @property
    def app_names(self) -> list[str]:
        return [app.name for app in self.apps]

    @property
    def lease_until(self) -> datetime.datetime | None:
        """
        Returns the earliest lease_until datetime of all apps in the environment.
        """
        leases = [app.lease_until for app in self.apps if app.lease_until]
        if not leases:
            return None

        return min(leases)

    @property
    def lease_info(self) -> LeaseInfo | None:
        if self.lease_until:
            return LeaseInfo(lease_until=self.lease_until)

        return None


@dataclass
class EnvironmentMetadata:
    """
    Shallow object for environment metadata.
    """

    name: str
    owner_email: str
    created_at: datetime.datetime
    lease_exclusion_window: str | None

    @staticmethod
    def from_configmap(configmap):
        body = json.loads(configmap.data["json"])
        owner = configmap.metadata.annotations.get("tails.com/owner")

        return EnvironmentMetadata(
            name=configmap.metadata.name,
            owner_email=owner,
            created_at=_datetime_from_str(body["created_at"]),
            lease_exclusion_window=(
                body.get("lease_exclusion_window", None)
            ),
        )


def _datetime_from_str(date_str: str) -> datetime.datetime:
    """
    This function provides backwards compatibility for 4 date formats:
    1. RFC3339 timespan: 2024-07-29T08:30:00+00:00-2024-07-29T16:00:00+00:00
    2. ISO 8601 format: 2021-09-01T12:00:00.000
    3. '%d-%m-%Y %H:%M:%S' format: 01-09-2021 12:00:00
    4. "%Y-%m-%dT%H:%M" format: 2021-09-01T12:00
    """
    # Check if it's a timespan first
    try:
        # This is not a nice way but I don't know a better one
        return datetime.datetime.fromisoformat(date_str[-25:])
    except ValueError:
        pass

    # Check if it's a normal ISO date string
    try:
        return datetime.datetime.fromisoformat(date_str)
    except ValueError:
        pass

    # Try the custom formats
    custom_formats = ["%d-%m-%Y %H:%M:%S", "%Y-%m-%dT%H:%M"]

    for fmt in custom_formats:
        try:
            return datetime.datetime.strptime(date_str, fmt)
        except ValueError:
            pass

    raise ValueError(
        f"Invalid date format: {date_str}. Expected ISO 8601, '%d-%m-%Y %H:%M:%S' or '%Y-%m-%dT%H:%M' format."
    )
 