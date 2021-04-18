from jsonpath_ng.ext import parse
from pharos import exceptions


class Lookup:

    PRE = "PRE"
    POST = "POST"
    name = None
    type = None

    def __init__(self, jsonpath_expr, field):
        self.field = field
        self.jsonpath_expr = jsonpath_expr

    def update_queryset(self, qs, value, op):
        raise NotImplementedError()

    def validate(self, obj, data):
        raise NotImplementedError


class ApiEqualLookup(Lookup):
    name = "equal"
    type = Lookup.PRE

    def update_queryset(self, qs, value):
        qs.api_kwargs[self.field.field_name] = value
        return qs


class LabelSelectorLookup(ApiEqualLookup):
    def update_queryset(self, qs, value):
        if "label_selector" in qs.api_kwargs:
            qs.api_kwargs["label_selector"] += f",{value}"
        else:
            qs.api_kwargs["label_selector"] = value


class JsonPathEqualLookup(Lookup):
    name = "equal"
    type = Lookup.POST

    def validate(self, obj, data):
        valid = obj == data
        if valid:
            return data
        raise exceptions.ValidationError()


class ApiInLookup(Lookup):
    name = "in"
    type = Lookup.PRE


class JsonPathInLookup(Lookup):
    name = "in"
    type = Lookup.POST

    def validate(self, obj, data):
        valid = obj in data
        if valid:
            return data
        raise exceptions.ValidationError()


class JsonPathContainsLookup(Lookup):
    name = "contains"
    type = Lookup.POST

    def validate(self, obj, data):
        valid = data in obj
        if valid:
            return data
        raise exceptions.ValidationError()


class JsonPathStartsWithLookup(Lookup):
    name = "startswith"
    type = Lookup.POST

    def validate(self, obj, data):
        valid = obj.startswith(data)
        if valid:
            return data
        raise exceptions.ValidationError()


class OwnerRefEqualLookup(Lookup):
    name = "equal"
    type = Lookup.POST

    def validate(self, obj, data):
        values = {data.k8s_object["metadata"]["uid"]}
        valid = bool({i.get("uid") for i in obj} & set(values))
        if valid:
            return data
        raise exceptions.ValidationError()


class OwnerRefInLookup(Lookup):
    name = "in"
    type = Lookup.POST

    def validate(self, obj, data):
        values = {owner.k8s_object["metadata"]["uid"] for owner in data}
        valid = bool({i.get("uid", None) for i in obj} & set(values))
        if valid:
            return data
        raise exceptions.ValidationError()


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
    json_path = True

    def __init__(self, path=None):
        self.path = path or self.path
        self.field_name = None
        self.valid_lookups = {}

        self.jsonpath_expr = None
        if self.path and self.json_path:
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


class JsonPathField(QueryField):
    lookups = [
        JsonPathEqualLookup,
        JsonPathInLookup,
        JsonPathContainsLookup,
        JsonPathStartsWithLookup,
    ]

    def get_value(self, obj):
        return find_jsonpath_value(self.jsonpath_expr, obj)


class K8sApiField(QueryField):
    lookups = [
        ApiEqualLookup,
        JsonPathInLookup,
        JsonPathContainsLookup,
        JsonPathStartsWithLookup,
    ]

    def get_value(self, obj):
        return find_jsonpath_value(self.jsonpath_expr, obj)


class OwnerRefField(QueryField):
    path = "$.metadata.ownerReferences[*].uid"
    lookups = [OwnerRefEqualLookup, OwnerRefInLookup]

    def get_value(self, obj):
        return obj["metadata"].get("ownerReferences")


class LabelField(QueryField):
    lookups = [LabelSelectorLookup]

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
