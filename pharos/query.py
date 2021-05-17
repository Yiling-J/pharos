import time
from pydoc import locate
from kubernetes.dynamic import exceptions as api_exceptions
from pharos import iterator
from pharos import exceptions
from pharos import models
from pharos import backend, jinja


variable_spec = {
    "apiVersion": "apiextensions.k8s.io/v1",
    "kind": "CustomResourceDefinition",
    "metadata": {"name": "variables.pharos.py"},
    "spec": {
        "group": "pharos.py",
        "versions": [
            {
                "name": "v1",
                "served": True,
                "storage": True,
                "schema": {
                    "openAPIV3Schema": {
                        "type": "object",
                        "properties": {"json": {"type": "object"}},
                    }
                },
            }
        ],
        "scope": "Cluster",
        "names": {"plural": "variables", "singular": "variable", "kind": "Variable"},
    },
}


class QuerySet:
    """Represent a lazy database lookup for a set of objects."""

    def __init__(self, model=None, using=None):
        self.model = model
        self._client = using
        self._result_cache = None
        self._query = []
        self.api_kwargs = {}
        self._limit = None

    @property
    def query(self):
        return self._query

    def using(self, client):
        self._client = client
        return self

    def filter(self, **kwargs):
        clone = self._clone()
        for k, v in kwargs.items():
            op = "equal"
            field = k
            if "__" in k:
                field, op = k.rsplit("__", 1)
            field = getattr(clone.model, field, None)
            if not field:
                raise exceptions.FieldDoesNotExist()
            clone._query.append({"field": field, "value": v, "op": op})
        return clone

    def all(self):
        return self._clone()

    def get(self, **kwargs):
        clone = self.filter(**kwargs)
        num = len(clone)
        if num == 1:
            return clone._result_cache[0]
        if not num:
            raise exceptions.ObjectDoesNotExist()
        raise exceptions.MultipleObjectsReturned()

    def _create_variable_crd(self):
        try:
            models.CustomResourceDefinition.objects.using(self._client).create(
                "variable_crd.yaml", {}, internal=True
            )
            time.sleep(0.1)
        except api_exceptions.ConflictError:
            pass

    def create(
        self, template, variables, internal=False, dry_run=False, namespace=None
    ):
        template_backend = backend.TemplateBackend()
        if internal:
            engine = jinja.JinjaEngine(self._client, internal=True)
        else:
            engine = locate(self._client.settings.template_engine)(self._client)
        template_backend.set_engine(engine)
        json_spec = template_backend.render(namespace, template, variables, internal)

        if json_spec["kind"] != self.model.Meta.kind:
            raise exceptions.ResourceNotMatch()

        client = self._client.dynamic_client
        api_spec = client.resources.get(
            api_version=self.model.Meta.api_version, kind=self.model.Meta.kind
        )

        if dry_run:
            response = api_spec.create(
                body=json_spec,
                namespace=namespace
                or json_spec["metadata"].get("namespace")
                or "default",
                query_params=[("dryRun", "All")],
            )
            instance = self.model(client=self._client, k8s_object=response.to_dict())
            return instance

        response = api_spec.create(
            body=json_spec,
            namespace=namespace or json_spec["metadata"].get("namespace") or "default",
        )
        instance = self.model(client=self._client, k8s_object=response.to_dict())
        if internal:
            return instance

        self._create_variable_crd()
        models.PharosVariable.objects.using(self._client).create(
            "variables.yaml",
            {"name": instance.variable_name, "value": variables},
            internal=True,
            namespace=namespace,
        )
        return instance

    def _update(
        self,
        namespace,
        template,
        variables,
        resource_version,
        internal=False,
        dry_run=False,
    ):
        template_backend = backend.TemplateBackend()
        if internal:
            engine = jinja.JinjaEngine(self._client, internal=True)
        else:
            engine = locate(self._client.settings.template_engine)(self._client)
        template_backend.set_engine(engine)
        json_spec = template_backend.render(namespace, template, variables, internal)
        json_spec["metadata"]["resourceVersion"] = resource_version
        client = self._client.dynamic_client
        api_spec = client.resources.get(
            api_version=self.model.Meta.api_version, kind=self.model.Meta.kind
        )
        query_params = [("dryRun", "All")] if dry_run else []
        response = api_spec.replace(
            body=json_spec,
            namespace=namespace or json_spec["metadata"].get("namespace") or "default",
            query_params=query_params,
        )

        return response.to_dict()

    def delete(self, name, namespace=None):
        client = self._client.dynamic_client
        api_spec = client.resources.get(
            api_version=self.model.Meta.api_version, kind=self.model.Meta.kind
        )
        return api_spec.delete(name, namespace)

    def limit(self, count):
        self._limit = count
        return self

    def __repr__(self):
        data = list(self)
        return "<%s %r>" % (self.__class__.__name__, data)

    def __len__(self):
        self._fetch_all()
        return len(self._result_cache)

    def __iter__(self):
        self._fetch_all()

        return iter(self._result_cache)

    def _get_result(self):
        client = self._client.dynamic_client

        if self._client.settings.disable_compress is False:
            self.api_kwargs["header_params"] = {"Accept-Encoding": "gzip"}

        pre_lookups = []
        post_lookups = []
        for i in self._query:
            lookup = i["field"].get_lookup(i["op"])
            if lookup.type == lookup.PRE:
                pre_lookups.append(
                    {"field": i["field"], "lookup": lookup, "rhs": i["value"]}
                )
            elif lookup.type == lookup.POST:
                post_lookups.append(
                    {"field": i["field"], "lookup": lookup, "rhs": i["value"]}
                )

        for lookup in pre_lookups:
            lookup["lookup"].update_queryset(self, lookup["rhs"])

        api_spec = client.resources.get(
            api_version=self.model.Meta.api_version, kind=self.model.Meta.kind
        )

        iterator_class = iterator.SimpleIterator
        if self._client.settings.enable_chunk:
            iterator_class = iterator.ChunkIterator

        api = iterator_class(self._client, api_spec)
        result = api.get(**self.api_kwargs)
        self._result_cache = result

        final = []
        for obj in result:
            valid = True
            for lookup in post_lookups:
                try:
                    value = lookup["field"].get_value(obj)
                    lookup["lookup"].validate(value, lookup["rhs"])
                except exceptions.ValidationError:
                    valid = False
                    break

            if valid is True:
                final.append(obj)
            if len(final) == self._limit:
                break

        self._result_cache = [
            self.model(client=self._client, k8s_object=i) for i in final
        ]
        return self._result_cache

    def _fetch_all(self):
        if not self._client:
            raise exceptions.ClientNotSet()

        if self._result_cache is None:
            self._get_result()

    def __getitem__(self, k):
        if not isinstance(k, (int, slice)):
            raise TypeError(
                "QuerySet indices must be integers or slices, not %s."
                % type(k).__name__
            )

        self._fetch_all()
        return self._result_cache[k]

    def _clone(self):
        c = self.__class__(
            model=self.model,
            using=self._client,
        )
        c._query = self._query
        c._limit = self._limit
        return c
