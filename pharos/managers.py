import inspect
from pharos.query import QuerySet


class BaseManager:

    def __get__(self, obj, model=None):
        self.model = model
        return self

    def __init__(self):
        self.model = None
        self.owner = None
        self.through = None
        self._client = None

    def __str__(self):
        """Return "app_label.model_label.manager_name"."""
        return '%s.%s' % (self.model._meta.label, self.name)

    def __class_getitem__(cls, *args, **kwargs):
        return cls

    @classmethod
    def _get_queryset_methods(cls, queryset_class):
        def create_method(name, method):
            def manager_method(self, *args, **kwargs):
                return getattr(self.get_queryset(), name)(*args, **kwargs)
            manager_method.__name__ = method.__name__
            manager_method.__doc__ = method.__doc__
            return manager_method

        new_methods = {}
        for name, method in inspect.getmembers(
                queryset_class, predicate=inspect.isfunction
        ):
            # Only copy missing methods.
            if hasattr(cls, name):
                continue
            new_methods[name] = create_method(name, method)
        return new_methods

    @classmethod
    def from_queryset(cls, queryset_class, class_name=None):
        if class_name is None:
            class_name = '%sFrom%s' % (cls.__name__, queryset_class.__name__)
        return type(class_name, (cls,), {
            '_queryset_class': queryset_class,
            **cls._get_queryset_methods(queryset_class),
        })

    def using(self, client):
        self._client = client
        return self

    def get_queryset(self):

        if not self._client:
            raise

        if not self.owner:
            return self._queryset_class(model=self.model,  using=self._client)

        selector = self.owner.selector
        if self.through:
            owners = self.through.objects.filter(
                selector=selector,
                owner=self.owner
            )
            return self._queryset_class(
                model=self.model,
                using=self._client,
            ).filter(owner__in=owners).filter(selector=selector)

        return self._queryset_class(
            model=self.model,
            using=self._client,
        ).filter(label=selector, owner=self.owner)


class Manager(BaseManager.from_queryset(QuerySet)):
    pass