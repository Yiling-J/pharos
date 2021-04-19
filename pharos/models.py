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


class Node(K8sModel):
    class Meta:
        api_version = "v1"
        kind = "Node"


class Pod(K8sModel):
    class Meta:
        api_version = "v1"
        kind = "Pod"


class ReplicaSet(K8sModel):
    pods = fields.RelatedField(to=Pod)

    class Meta:
        api_version = "v1"
        kind = "ReplicaSet"


class Deployment(K8sModel):
    replicasets = fields.RelatedField(to=ReplicaSet)
    pods = fields.RelatedField(to=Pod, through=ReplicaSet)

    class Meta:
        api_version = "v1"
        kind = "Deployment"


class StatefulSet(K8sModel):

    class Meta:
        api_version = "v1"
        kind = "StatefulSet"


class ConfigMap(K8sModel):

    class Meta:
        api_version = "v1"
        kind = "ConfigMap"


class CronJob(K8sModel):

    class Meta:
        api_version = "batch/v2alpha1"
        kind = "CronJob"


class DaemonSet(K8sModel):

    class Meta:
        api_version = "v1"
        kind = "DaemonSet"


class Endpoints(K8sModel):

    class Meta:
        api_version = "v1"
        kind = "Endpoints"


class Event(K8sModel):

    class Meta:
        api_version = "v1"
        kind = "Event"


class Ingress(K8sModel):

    class Meta:
        api_version = "networking.k8s.io/v1beta1"
        kind = "Ingress"


class Job(K8sModel):

    class Meta:
        api_version = "batch/v1"
        kind = "Job"


class Namespace(K8sModel):

    class Meta:
        api_version = "v1"
        kind = "Namespace"


class Service(K8sModel):
    pods = fields.RelatedField(to=Pod, skip_owner=True)
    selector = fields.ServiceSelectorField()

    class Meta:
        api_version = "v1"
        kind = "Service"


class PersistentVolume(K8sModel):

    class Meta:
        api_version = "v1"
        kind = "PersistentVolume"


class PersistentVolumeClaim(K8sModel):

    class Meta:
        api_version = "v1"
        kind = "PersistentVolumeClaim"


class HorizontalPodAutoscaler(K8sModel):

    class Meta:
        api_version = "autoscaling/v1"
        kind = "HorizontalPodAutoscaler"
