from pharos import managers
from pharos import operators


class RelatedField:
    def __init__(self, to, through=None):
        self.to = to
        if through:
            self.through = through

    def __get__(self, obj, type=None):
        manager = self.to.objects
        clone = manager.__class__()
        clone.model = manager.model
        clone.owner = obj
        clone._client = obj._client

        if self.through:
            clone.through = self.through
        return clone


class QueryField:
    def __init__(self, operator=None, path=None):
        self.operator = operator(path=path) or operators.JsonPathOperator(path=path)
        self.path = path
        self.field_name = None

    def __get__(self, obj, type=None):
        if not obj:
            return self

        return self.operator.get_value(obj)

    def __set_name__(self, owner, name):
        self.field_name = name
        self.operator.field_name = name


class K8sModel:
    name = QueryField(operator=operators.ClientValueOperator, path="metadata.name")
    namespace = QueryField(
        operator=operators.ClientValueOperator, path="metadata.namespace"
    )
    selector = QueryField(operator=operators.SelectorOperator)
    owner = QueryField(operator=operators.OwnerRefOperator)

    objects = managers.Manager()
    client = None

    def __init__(self, k8s_object, client):
        self.k8s_object = k8s_object
        self._client = client


class ReplicaSet(K8sModel):
    class Meta:
        api_version = "v1"
        kind = "ReplicaSet"


class Pod(K8sModel):
    class Meta:
        api_version = "v1"
        kind = "Pod"


class Container(K8sModel):
    pod = RelatedField(Pod)

    class Meta:
        api_version = "v1"
        kind = "Container"


class Deployment(K8sModel):
    replicasets = RelatedField(to=ReplicaSet)
    pods = RelatedField(to=Pod, through=ReplicaSet)

    class Meta:
        api_version = "v1"
        kind = "Deployment"
