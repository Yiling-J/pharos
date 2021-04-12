from pharos import iterator
from pharos import exceptions


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
            op = "EQUAL"
            field = k
            if "__" in k:
                field, op = k.rsplit("__", 1)
                op = op.upper()
            field = getattr(clone.model, field, None)
            if not field:
                raise exceptions.FieldDoesNotExist()
            clone._query.append({"operator": field.operator, "value": v, "op": op})
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

        for item in [i for i in self._query if i["operator"].type == "PRE"]:
            item["operator"].update_queryset(self, item["value"], item["op"])
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
        post_operators = [i for i in self._query if i["operator"].type == "POST"]
        for obj in result:
            valid = True
            if len(final) == self._limit:
                break
            for i in post_operators:
                try:
                    obj = i["operator"].validate(obj, i["value"], i["op"])
                except exceptions.ValidationError:
                    valid = False
                    break
            if valid is True:
                final.append(obj)

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
        assert (not isinstance(k, slice) and (k >= 0)) or (
            isinstance(k, slice)
            and (k.start is None or k.start >= 0)
            and (k.stop is None or k.stop >= 0)
        ), "Negative indexing is not supported."

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
