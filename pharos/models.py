import yaml
from pharos import managers
from pharos import fields
from pharos import utils


class Model:
    name = fields.K8sApiField(path="metadata.name")
    namespace = fields.K8sApiField(path="metadata.namespace")
    selector = fields.LabelSelectorField()
    field_selector = fields.FieldSelectorField()
    owner = fields.OwnerRefField()
    variable = fields.RelatedField(
        to="pharos.models.PharosVariable",
        from_field="variable_name",
        to_field="name",
        skip_owner=True,
    )
    template = fields.JsonPathField(path='metadata.annotations."pharos.py/template"')

    objects = managers.Manager()
    _client = None

    def __init__(self, k8s_object, client):
        self.k8s_object = utils.ReadOnlyDict(k8s_object)
        self._client = client

    def __repr__(self):
        return f"<{self.Meta.kind}: {self.name}>"

    def __str__(self):
        return self.name or ""

    def refresh(self):
        client = self._client.dynamic_client
        api_spec = client.resources.get(
            api_version=self.Meta.api_version, kind=self.Meta.kind
        )
        result = api_spec.get(name=self.name, namespace=self.namespace).to_dict()
        self.k8s_object = utils.ReadOnlyDict(result)

    @property
    def yaml(self):
        return yaml.dump(self.k8s_object, default_flow_style=False)

    @property
    def variable_name(self):
        return f"{self.name}-{self.namespace}"


class Pod(Model):
    class Meta:
        api_version = "v1"
        kind = "Pod"


class Node(Model):
    pods = fields.RelatedField(to=Pod, to_field="field_selector", skip_owner=True)

    class Meta:
        api_version = "v1"
        kind = "Node"

    @property
    def selector(self):
        return f"spec.nodeName={self.name}"


class ReplicaSet(Model):
    pods = fields.RelatedField(to=Pod)

    class Meta:
        api_version = "v1"
        kind = "ReplicaSet"


class Deployment(Model):
    replicasets = fields.RelatedField(to=ReplicaSet)
    pods = fields.RelatedField(to=Pod, through=ReplicaSet)

    class Meta:
        api_version = "v1"
        kind = "Deployment"


class StatefulSet(Model):
    class Meta:
        api_version = "v1"
        kind = "StatefulSet"


class ConfigMap(Model):
    class Meta:
        api_version = "v1"
        kind = "ConfigMap"


class CronJob(Model):
    class Meta:
        api_version = "batch/v2alpha1"
        kind = "CronJob"


class DaemonSet(Model):
    class Meta:
        api_version = "v1"
        kind = "DaemonSet"


class Endpoints(Model):
    class Meta:
        api_version = "v1"
        kind = "Endpoints"


class Event(Model):
    class Meta:
        api_version = "v1"
        kind = "Event"


class Ingress(Model):
    class Meta:
        api_version = "networking.k8s.io/v1beta1"
        kind = "Ingress"


class Job(Model):
    class Meta:
        api_version = "batch/v1"
        kind = "Job"


class Namespace(Model):
    class Meta:
        api_version = "v1"
        kind = "Namespace"


class Service(Model):
    pods = fields.RelatedField(to=Pod, skip_owner=True)
    selector = fields.ServiceSelectorField()

    class Meta:
        api_version = "v1"
        kind = "Service"


class PersistentVolume(Model):
    class Meta:
        api_version = "v1"
        kind = "PersistentVolume"


class PersistentVolumeClaim(Model):
    class Meta:
        api_version = "v1"
        kind = "PersistentVolumeClaim"


class HorizontalPodAutoscaler(Model):
    class Meta:
        api_version = "autoscaling/v2beta2"
        kind = "HorizontalPodAutoscaler"


class CustomResourceDefinition(Model):
    class Meta:
        api_version = "apiextensions.k8s.io/v1"
        kind = "CustomResourceDefinition"


class PharosVariable(Model):
    data = fields.JsonPathField(path="json")

    class Meta:
        api_version = "pharos.py/v1"
        kind = "Variable"
