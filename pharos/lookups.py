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


class FieldSelectorLookup(ApiEqualLookup):
    def update_queryset(self, qs, value):
        if "field_selector" in qs.api_kwargs:
            qs.api_kwargs["field_selector"] += f",{value}"
        else:
            qs.api_kwargs["field_selector"] = value


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
        if type(obj) == list and type(data) in (list, tuple, set):
            valid = set(data) <= set(obj)
        else:
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


class JsonPathGreaterLookup(Lookup):
    name = "gt"
    type = Lookup.POST

    def validate(self, obj, data):
        valid = obj > data
        if valid:
            return data
        raise exceptions.ValidationError()


class JsonPathLessLookup(Lookup):
    name = "lt"
    type = Lookup.POST

    def validate(self, obj, data):
        valid = obj < data
        if valid:
            return data
        raise exceptions.ValidationError()


class JsonPathGreaterEqualLookup(Lookup):
    name = "gte"
    type = Lookup.POST

    def validate(self, obj, data):
        valid = obj >= data
        if valid:
            return data
        raise exceptions.ValidationError()


class JsonPathLessEqualLookup(Lookup):
    name = "lte"
    type = Lookup.POST

    def validate(self, obj, data):
        valid = obj <= data
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
