class TemplateBackend:
    engine = None
    prefix = "pharos.py"

    def render(self, namespace, template, variables, internal):
        json_spec = self.engine.render(template, variables)
        if not internal:
            self.update_annotations(namespace, json_spec, template, variables)
        return json_spec

    def update_annotations(self, namespace, json_spec, template, variables):
        extra_annotations = {
            f"{self.prefix}/template": template,
            f"{self.prefix}/variable": f'{json_spec["kind"].lower()}-{json_spec["metadata"]["name"]}-{namespace or json_spec["metadata"].get("namespace") or "default"}',
        }
        if (
            "annotations" in json_spec["metadata"]
            and json_spec["metadata"]["annotations"]
        ):
            json_spec["metadata"]["annotations"].update(extra_annotations)
        else:
            json_spec["metadata"]["annotations"] = extra_annotations

    def set_engine(self, engine):
        self.engine = engine
