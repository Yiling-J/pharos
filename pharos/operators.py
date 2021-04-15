from jsonpath_ng.ext import parse
from pharos import exceptions


class BaseOperator:
    json_path = True
    type = None

    def __init__(self, path):
        self.path = path
        if self.path and self.json_path:
            self.jsonpath_expr = parse(self.path)

    def get_value(self, obj):
        raise

    def get_type(self, op):
        if self.type:
            return self.type
        return self._get_type_from_op(op)

    def _get_type_from_op(self, op):
        raise NotImplementedError()


class PreOperator(BaseOperator):
    type = 'PRE'

    def update_queryset(self, qs, value, op):
        raise NotImplementedError()


class PostOperator(BaseOperator):
    type = 'POST'

    def validate(self, obj, data, op):
        raise NotImplementedError


class SelectorOperator(PreOperator):

    def get_value(self, obj):
        data = obj.k8s_object["spec"].get("selector")
        if data:
            labels = [f"{k}={v}" for k, v in data.get("matchLabels", {}).items()]
            expressions = [
                f'{i["key"]} {i["operator"]} {tuple(i["values"])}'
                for i in data.get("matchExpressions", [])
            ]
            return ",".join(labels + expressions)
        return None

    def update_queryset(self, qs, value, op):
        if "label_selector" in qs.api_kwargs:
            qs.api_kwargs["label_selector"] += f",{value}"
        else:
            qs.api_kwargs["label_selector"] = value


class ClientValueOperator(BaseOperator):

    def _get_type_from_op(self, op):
        if op == 'EQUAL':
            return 'PRE'
        return 'POST'

    def get_value(self, obj):
        matches = self.jsonpath_expr.find(obj.k8s_object)
        return matches[0].value if matches else None

    def update_queryset(self, qs, value, op):
        qs.api_kwargs[self.field_name] = value
        return qs

    def validate(self, obj, data, op):
        if op == "IN":
            valid = find_jsonpath_value(self.jsonpath_expr, obj) in data
        elif op == 'CONTAINS':
            valid = data in find_jsonpath_value(self.jsonpath_expr, obj)
        elif op == 'STARTSWITH':
            valid = find_jsonpath_value(self.jsonpath_expr, obj).startswith(data)
        else:
            raise exceptions.OperatorNotValid()
        if not valid:
            raise exceptions.ValidationError()
        return obj


def find_jsonpath_value(jsonpath_expr, data):
    matches = [i.value for i in jsonpath_expr.find(data)]
    return matches[0] if matches else None


class JsonPathOperator(PostOperator):

    def get_value(self, obj):
        matches = self.jsonpath_expr.find(obj.k8s_object)
        return matches[0].value if matches else None

    def validate(self, obj, data, op):
        if op == "EQUAL":
            valid = find_jsonpath_value(self.jsonpath_expr, obj) == data
        elif op == "IN":
            valid = find_jsonpath_value(self.jsonpath_expr, obj) in data
        elif op == 'CONTAINS':
            valid = data in find_jsonpath_value(self.jsonpath_expr, obj)
        elif op == 'STARTSWITH':
            valid = find_jsonpath_value(self.jsonpath_expr, obj).startswith(data)
        else:
            raise exceptions.OperatorNotValid()
        if not valid:
            raise exceptions.ValidationError()
        return obj


class OwnerRefOperator(PostOperator):

    def __init__(self, path):
        self.path = "$.metadata.ownerReferences[*].uid"
        self.jsonpath_expr = parse(self.path)

    def get_value(self, obj):
        return obj["metadata"].get("ownerReferences")

    def validate(self, obj, data, op):
        if op == "IN":
            values = {owner.k8s_object["metadata"]["uid"] for owner in data}
        else:
            values = {data.k8s_object["metadata"]["uid"]}

        valid = bool({i.value for i in self.jsonpath_expr.find(obj)} & set(values))
        if not valid:
            raise exceptions.ValidationError()
        return obj
