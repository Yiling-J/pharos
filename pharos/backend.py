class TemplateBackend:
    engine = None
    prefix = "pharos"

    def render(self, template, variables, internal):
        json_spec = self.engine.render(template, variables)
        if not internal:
            self.update_annotations(json_spec, template, variables)
        return json_spec

    def update_annotations(self, json_spec, template, variables):
        extra_annotations = {
            f"{self.prefix}/template-path": template,
            f"{self.prefix}/variable-resource": f'{json_spec["metadata"]["name"]}-{json_spec["metadata"].get("namespace", "default")}',
        }
        if "annotations" in json_spec["metadata"]:
            json_spec["metadata"]["annotations"].update(extra_annotations)
        else:
            json_spec["metadata"]["annotations"] = extra_annotations

    def set_engine(self, engine):
        self.engine = engine
