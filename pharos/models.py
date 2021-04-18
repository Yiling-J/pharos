from pharos import managers
from pharos import fields


class K8sModel:
    name = fields.K8sApiField(path="metadata.name")
    namespace = fields.K8sApiField(path="metadata.namespace")
    selector = fields.LabelSelectorField()
    field_selector = fields.FieldSelectorField()
    owner = fields.OwnerRefField()

    objects = managers.Manager()
    client = None

    def __init__(self, k8s_object, client):
        self.k8s_object = k8s_object
        self._client = client

    def __repr__(self):
        return f"<{self.Meta.kind}: {self.name}>"

    def __str__(self):
        return self.name or ""


class ReplicaSet(K8sModel):
    class Meta:
        api_version = "v1"
        kind = "ReplicaSet"


class Pod(K8sModel):
    class Meta:
        api_version = "v1"
        kind = "Pod"


class Container(K8sModel):
    pod = fields.RelatedField(Pod)

    class Meta:
        api_version = "v1"
        kind = "Container"


class Deployment(K8sModel):
    replicasets = fields.RelatedField(to=ReplicaSet)
    pods = fields.RelatedField(to=Pod, through=ReplicaSet)

    class Meta:
        api_version = "v1"
        kind = "Deployment"
