from jsonpath_ng.ext import parse
from pharos import lookups
from pharos import exceptions


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
    operator_class = None
    path = None
    lookups = []

    def __init__(self, path=None):
        self.path = path or self.path
        self.field_name = None
        self.valid_lookups = {}

        self.jsonpath_expr = None
        if self.path:
            self.jsonpath_expr = parse(self.path)

        for lookup in self.lookups:
            self.valid_lookups[lookup.name] = lookup(self.jsonpath_expr, field=self)

    def __get__(self, obj, type=None):
        if not obj:
            return self

        return self.get_value(obj.k8s_object)

    def __set_name__(self, owner, name):
        self.field_name = name

    def get_value(self, obj):
        raise NotImplementedError()

    def get_lookup(self, op):
        return self.valid_lookups[op]

    @classmethod
    def add_lookup(cls, lookup):
        if issubclass(lookup, lookups.Lookup):
            cls.lookups.append(lookup)
            return
        raise exceptions.LookupNotValid()


class JsonPathField(QueryField):
    lookups = [
        lookups.JsonPathEqualLookup,
        lookups.JsonPathInLookup,
        lookups.JsonPathContainsLookup,
        lookups.JsonPathStartsWithLookup,
    ]

    def get_value(self, obj):
        return find_jsonpath_value(self.jsonpath_expr, obj)


class K8sApiField(QueryField):
    lookups = [
        lookups.ApiEqualLookup,
        lookups.JsonPathInLookup,
        lookups.JsonPathContainsLookup,
        lookups.JsonPathStartsWithLookup,
    ]

    def get_value(self, obj):
        return find_jsonpath_value(self.jsonpath_expr, obj)


class OwnerRefField(QueryField):
    path = "$.metadata.ownerReferences[*].uid"
    lookups = [lookups.OwnerRefEqualLookup, lookups.OwnerRefInLookup]

    def get_value(self, obj):
        return obj["metadata"].get("ownerReferences")


class LabelField(QueryField):
    lookups = [lookups.LabelSelectorLookup]

    def get_value(self, obj):
        data = obj["spec"].get("selector")
        if data:
            labels = [f"{k}={v}" for k, v in data.get("matchLabels", {}).items()]
            expressions = [
                f'{i["key"]} {i["operator"]} {tuple(i["values"])}'
                for i in data.get("matchExpressions", [])
            ]
            return ",".join(labels + expressions)
        return None


def find_jsonpath_value(jsonpath_expr, data):
    matches = [i.value for i in jsonpath_expr.find(data)]
    return matches[0] if matches else None
