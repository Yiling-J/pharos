import yaml
from jinja2 import Environment, PackageLoader, select_autoescape


pharos_env = Environment(
    loader=PackageLoader('pharos', 'templates'),
    autoescape=select_autoescape(['html', 'xml'])
)


def to_yaml(value):
    return yaml.dump(value, default_flow_style=False)


pharos_env.filters['yaml'] = to_yaml


class JinjaEngine:

    def __init__(self, internal=False):
        if internal:
            self.env = pharos_env
        else:
            self.env = ''

    def render(self, template_path, variables):
        template = self.env.get_template(template_path)
        yaml_spec = template.render(**variables)
        print(yaml_spec)
        return yaml.safe_load(yaml_spec)
