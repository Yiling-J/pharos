from pharos import managers
from pharos import fields


class Model:
    name = fields.K8sApiField(path="metadata.name")
    namespace = fields.K8sApiField(path="metadata.namespace")
    selector = fields.LabelSelectorField()
    field_selector = fields.FieldSelectorField()
    owner = fields.OwnerRefField()

    objects = managers.Manager()
    _client = None

    def __init__(self, k8s_object, client):
        self.k8s_object = k8s_object
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
        self.k8s_object = result


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
