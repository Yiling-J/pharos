import json
import hashlib


class TemplateBackend:
    engine = None
    prefix = "pharos"

    def render(self, template, variables, raw):
        json_spec = self.engine.render(template, variables)
        if not raw:
            self.update_annotations(json_spec, template, variables)
        return json_spec

    def get_variable_hash(self, variables):
        return hashlib.sha256(json.dumps(variables).encode()).hexdigest()

    def update_annotations(self, json_spec, template, variables):
        variable_hash = self.get_variable_hash(variables)
        extra_annotations = {
            f"{self.prefix}/template-path": template,
            f"{self.prefix}/variable-resource": f'{json_spec["metadata"]["name"]}-{variable_hash}',
        }
        if "annotations" in json_spec["metadata"]:
            json_spec["metadata"]["annotations"].update(extra_annotations)
        else:
            json_spec["metadata"]["annotations"] = extra_annotations

    def set_engine(self, engine):
        self.engine = engine
