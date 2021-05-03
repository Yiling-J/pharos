import yaml
from jinja2 import Environment, PackageLoader


def to_yaml(value):
    return yaml.dump(value, default_flow_style=False)


class JinjaEngine:
    def __init__(self, client, internal=False):
        loader = client.settings.jinja_loader
        if internal:
            loader = PackageLoader("pharos", "templates")
        elif not loader:
            raise
        self.env = Environment(loader=loader)
        self.env.filters["yaml"] = to_yaml

    def render(self, template_path, variables):
        template = self.env.get_template(template_path)
        yaml_spec = template.render(**variables)
        return yaml.safe_load(yaml_spec)
