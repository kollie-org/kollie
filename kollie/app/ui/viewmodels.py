from abc import ABC, abstractmethod

from fastapi.templating import Jinja2Templates

from kollie.models import KollieApp


class ResourceView(ABC):

    @property
    @abstractmethod
    def template(self) -> str:
        """
        The template to render the view.

        Returns:
            str: The template path.
        """

    @abstractmethod
    def build_context(self) -> dict:
        """
        Returns a dictionary with the information to render in the template.

        Returns:
            dict: The information to render.
        """

    def render(self, templates: Jinja2Templates) -> str:
        """
        Renders the view.

        Returns:
            str: The rendered view.
        """
        context = self.build_context()
        template = templates.env.get_template(self.template)

        return template.render(**context)


class IngressView(ResourceView):

    template = "/apps/ingress.jinja2"

    def __init__(self, model: KollieApp):
        self.model = model

    def build_context(self) -> dict:
        """
        Returns a dictionary with the information to render in the template.

        Args:
            model (KollieApp): The app model.

        Returns:
            dict: The information to render.
        """
        return {"urls": self.model.urls}


def render_resources(model: KollieApp, templates: Jinja2Templates) -> list[str]:
    """
    Returns the views for the app resources.

    Args:
        model (KollieApp): The app model.

    Returns:
        List[str]: The rendered views.
    """
    views = [IngressView]  # Add any new view here

    rendered_views = []

    for view in views:
        if model.urls:
            rendered_views.append(view(model).render(templates))

    return rendered_views
