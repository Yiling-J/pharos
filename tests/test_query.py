import yaml
from unittest import TestCase, mock
from jinja2 import PackageLoader, Environment, FileSystemLoader
from kubernetes.dynamic import exceptions as api_exceptions
from pharos import models, fields, exceptions, lookups, backend, jinja
from pharos.jinja import to_yaml
from pharos.backend import TemplateBackend


class BaseCase(TestCase):
    def setUp(self):
        self.dynamic_client = mock.Mock()
        self.client = mock.Mock()
        self.client.settings.enable_chunk = True
        self.client.settings.chunk_size = 100
        self.client.settings.jinja_loader = PackageLoader("tests", "./")
        self.client.settings.template_engine = "pharos.jinja.JinjaEngine"
        self.client.dynamic_client = self.dynamic_client


class DeploymentTestCase(BaseCase):
    def test_no_client(self):
        with self.assertRaises(exceptions.ClientNotSet):
            len(models.Deployment.objects.all())

    def test_chunk_iterator(self):
        mock_response = mock.Mock()
        response_lambda = lambda token: {
            "metadata": {"continue": token},
            "items": [
                {
                    "id": token,
                    "metadata": {
                        "ownerReferences": [{"kind": "Apple", "uid": "123"}],
                        "name": "test",
                    },
                }
            ],
        }

        # should call 6 times, and get END signal, so 7 won't be called
        mock_response.to_dict.side_effect = [
            response_lambda(f"{i}") for i in [1, 2, 3, 4, 5, "END", 7]
        ]
        self.dynamic_client.resources.get.return_value.get.return_value = mock_response
        query = models.Deployment.objects.using(self.client).all()
        self.assertEqual(len(query), 6)
        expected_call = [
            mock.call.get(_continue=None, limit=100),
            mock.call.get(_continue="1", limit=100),
            mock.call.get(_continue="2", limit=100),
            mock.call.get(_continue="3", limit=100),
            mock.call.get(_continue="4", limit=100),
            mock.call.get(_continue="5", limit=100),
        ]
        self.assertEqual(
            self.dynamic_client.resources.get.return_value.method_calls, expected_call
        )

    def test_limit_with_iterator(self):
        mock_response = mock.Mock()
        response_lambda = lambda token: {
            "metadata": {"continue": token},
            "items": [
                {
                    "id": token,
                    "metadata": {
                        "ownerReferences": [{"kind": "Apple", "uid": "123"}],
                        "name": "test",
                    },
                }
            ],
        }

        # should call 3 times only
        mock_response.to_dict.side_effect = [
            response_lambda(f"{i}") for i in [1, 2, 3, 4, 5, "END", 7]
        ]
        self.dynamic_client.resources.get.return_value.get.return_value = mock_response
        query = models.Deployment.objects.using(self.client).limit(3)
        self.assertEqual(len(query), 3)
        expected_call = [
            mock.call.get(_continue=None, limit=100),
            mock.call.get(_continue="1", limit=100),
            mock.call.get(_continue="2", limit=100),
        ]
        self.assertEqual(
            self.dynamic_client.resources.get.return_value.method_calls, expected_call
        )

    def test_deployment_query_basic(self):
        test_cases = [
            {
                "query": models.Deployment.objects.using(self.client).all(),
                "api_call": {},
            },
            {
                "query": models.Deployment.objects.using(self.client).filter(
                    name="apple"
                ),
                "api_call": {
                    "name": "apple",
                },
            },
            {
                "query": models.Deployment.objects.using(self.client).filter(
                    name="apple", namespace="orange"
                ),
                "api_call": {
                    "name": "apple",
                    "namespace": "orange",
                },
            },
            {
                "query": models.Deployment.objects.using(self.client)
                .filter(name="apple")
                .filter(namespace="orange"),
                "api_call": {
                    "name": "apple",
                    "namespace": "orange",
                },
            },
            {
                "query": models.Deployment.objects.using(self.client).filter(
                    selector="app in (a)"
                ),
                "api_call": {
                    "label_selector": "app in (a)",
                },
            },
            {
                "query": models.Deployment.objects.using(self.client)
                .filter(selector="app in (a)")
                .filter(selector="app=b"),
                "api_call": {
                    "label_selector": "app in (a),app=b",
                },
            },
            {
                "query": models.Deployment.objects.using(self.client).filter(
                    field_selector="name=foo"
                ),
                "api_call": {
                    "field_selector": "name=foo",
                },
            },
            {
                "query": models.Deployment.objects.using(self.client)
                .filter(field_selector="name=foo")
                .filter(field_selector="type=bar"),
                "api_call": {
                    "field_selector": "name=foo,type=bar",
                },
            },
        ]
        self.dynamic_client.resources.get.return_value.get.return_value.to_dict.side_effect = lambda: {
            "metadata": {},
            "items": ["test"],
        }
        for case in test_cases:
            with self.subTest(case=case):
                len(case["query"])
                self.assertEqual(
                    self.dynamic_client.resources.method_calls,
                    [mock.call.get(api_version="v1", kind="Deployment")],
                )
                self.assertEqual(
                    self.dynamic_client.resources.get.return_value.method_calls,
                    [mock.call.get(**case["api_call"], _continue=None, limit=100)],
                )
                self.dynamic_client.reset_mock()

        models.Deployment.objects.using(self.client).get(
            name="apple", namespace="orange"
        )
        self.assertEqual(
            self.dynamic_client.resources.get.return_value.method_calls,
            [
                mock.call.get(
                    name="apple", namespace="orange", _continue=None, limit=100
                )
            ],
        )

    def test_owner(self):
        mock_data = {"kind": "Apple", "metadata": {"uid": "123"}}
        mock_owner = models.Deployment(client=None, k8s_object=mock_data)

        mock_response = mock.Mock()
        mock_response.to_dict.side_effect = lambda: {
            "metadata": {},
            "items": [
                {
                    "id": 1,
                    "metadata": {
                        "ownerReferences": [{"kind": "Apple", "uid": "123"}],
                        "name": "test",
                    },
                },
                {
                    "id": 2,
                    "metadata": {"ownerReferences": [{"kind": "Appl", "uid": "124"}]},
                },
                {
                    "id": 3,
                    "metadata": {"ownerReferences": [{"kind": "Apple", "uid": "125"}]},
                },
                {"id": 4, "metadata": {"ownerReferences": [{"kind": "Apple"}]}},
                {
                    "id": 6,
                    "metadata": {"ownerReferences": [{"kind": "Apple", "uid": "123"}]},
                },
            ],
        }
        self.dynamic_client.resources.get.return_value.get.return_value = mock_response
        query = models.Deployment.objects.using(self.client).filter(owner=mock_owner)
        self.assertEqual(len(query), 2)

        mock_owner2 = models.Deployment(
            client=None, k8s_object={"kind": "Apple", "metadata": {"uid": "124"}}
        )

        query = models.Deployment.objects.using(self.client).filter(
            owner__in=[mock_owner, mock_owner2]
        )
        self.assertEqual(len(query), 3)

        deployment = query[0]
        self.assertEqual(deployment.name, "test")

    def test_deployment_pods(self):
        deployment = models.Deployment(
            client=self.client,
            k8s_object={
                "metadata": {"uid": "123"},
                "spec": {"selector": {"matchLabels": {"app": "test"}}},
            },
        )
        mock_rs_response = mock.Mock()
        mock_rs_response.to_dict.return_value = {
            "metadata": {},
            "items": [
                {
                    "id": 1,
                    "metadata": {
                        "ownerReferences": [{"kind": "ReplicaSet", "uid": "123"}],
                        "uid": "234",
                    },
                },
                {
                    "id": 2,
                    "metadata": {
                        "ownerReferences": [{"kind": "ReplicaSet", "uid": "124"}],
                        "uid": "235",
                    },
                },
                {
                    "id": 3,
                    "metadata": {
                        "ownerReferences": [{"kind": "ReplicaSet", "uid": "123"}],
                        "uid": "236",
                    },
                },
            ],
        }

        mock_pod_response = mock.Mock()
        mock_pod_response.to_dict.return_value = {
            "metadata": {},
            "items": [
                {
                    "id": 1,
                    "metadata": {
                        "ownerReferences": [{"kind": "ReplicaSet", "uid": "234"}]
                    },
                },
                {
                    "id": 2,
                    "metadata": {
                        "ownerReferences": [{"kind": "ReplicaSet", "uid": "235"}]
                    },
                },
                {"id": 4, "metadata": {"ownerReferences": [{"kind": "ReplicaSet"}]}},
            ],
        }

        # pod come first because owner filter is POST operator
        self.dynamic_client.resources.get.return_value.get.side_effect = [
            mock_pod_response,
            mock_rs_response,
        ]

        self.assertEqual(len(deployment.pods.all()), 1)

    def test_refresh(self):
        deployment = models.Deployment(
            client=self.client,
            k8s_object={
                "metadata": {"uid": "123", "name": "foo"},
                "spec": {"selector": {"matchLabels": {"app": "test"}}},
            },
        )
        self.assertEqual(deployment.name, "foo")
        mock_response = mock.Mock()
        mock_response.to_dict.side_effect = lambda: {"metadata": {"name": "bar"}}
        self.dynamic_client.resources.get.return_value.get.return_value = mock_response
        deployment.refresh()
        self.assertEqual(deployment.name, "bar")

    def test_delete(self):
        deployment = models.Deployment(
            client=self.client,
            k8s_object={
                "metadata": {
                    "name": "nginx-deployment",
                    "annotations": {
                        "deployment.kubernetes.io/revision": "1",
                        "pharos.py/template": "test.yaml",
                        "pharos.py/variable": "deployment-nginx-deployment-default",
                    },
                    "spec": {"selector": {"matchLabels": {"app": "test"}}},
                }
            },
        )
        mock_response = {
            "metadata": {
                "name": "nginx-deployment",
                "namespace": "default",
                "annotations": {
                    "deployment.kubernetes.io/revision": "1",
                    "pharos.py/template": "test.yaml",
                    "pharos.py/variable": "deployment-nginx-deployment-default",
                },
            },
            "json": {"label_name": "foo"},
        }
        self.dynamic_client.resources.get.return_value.get.return_value.to_dict.return_value = (
            mock_response
        )

        deployment.delete()
        self.assertSequenceEqual(
            self.dynamic_client.resources.method_calls,
            [
                mock.call.get(api_version="v1", kind="Deployment"),
                mock.call.get(api_version="pharos.py/v1", kind="Variable"),
                mock.call.get(api_version="v1", kind="Deployment"),
            ],
        )
        self.assertSequenceEqual(
            self.dynamic_client.resources.get.return_value.method_calls,
            [
                mock.call.get(name="nginx-deployment", namespace="default"),
                mock.call.delete("deployment-nginx-deployment-default", None),
                mock.call.delete("nginx-deployment", "default"),
            ],
        )

    def test_create_deployment_wrong_resource(self):
        mock_response = {
            "metadata": {
                "name": "foobar",
                "namespace": "default",
                "annotations": {"pharos.py/template": "test.yaml"},
            }
        }
        self.dynamic_client.resources.get.return_value.create.return_value.to_dict.return_value = (
            mock_response
        )
        with self.assertRaises(exceptions.ResourceNotMatch):
            models.Service.objects.using(self.client).create(
                "test.yaml", {"label_name": "foo"}
            )


class ServicePodsTestCase(BaseCase):
    def test_service_pods(self):
        service = models.Service(
            client=self.client,
            k8s_object={
                "metadata": {"uid": "123"},
                "spec": {"selector": {"foo": "bar"}},
            },
        )
        mock_rs_response = mock.Mock()
        mock_rs_response.to_dict.return_value = {}
        self.dynamic_client.resources.get.return_value.get.return_value = (
            mock_rs_response
        )
        len(service.pods.all())
        self.assertEqual(
            self.dynamic_client.resources.get.return_value.method_calls,
            [mock.call.get(_continue=None, label_selector="foo=bar", limit=100, namespace=None)],
        )


class CustomLookup(lookups.Lookup):
    name = "foo"
    type = lookups.Lookup.POST

    def validate(self, obj, data):
        return True


fields.JsonPathField.add_lookup(CustomLookup)


class CustomModel(models.Model):
    id = fields.JsonPathField(path="id")
    task = fields.JsonPathField(path="job.task")

    class Meta:
        api_version = "v1"
        kind = "CustomModel"


class CustomModelTestCase(BaseCase):
    def test_custom_model(self):
        mock_data = {
            "kind": "CustomModel",
            "job": {"task": "task1"},
            "metadata": {"name": "custom", "namespace": "default"},
        }
        mock_obj = CustomModel(client=None, k8s_object=mock_data)

        self.assertEqual(mock_obj.task, "task1")
        self.assertEqual(mock_obj.name, "custom")
        self.assertEqual(mock_obj.namespace, "default")

    def test_custom_filed_filter(self):
        mock_response = mock.Mock()
        mock_response.to_dict.side_effect = lambda: {
            "metadata": {},
            "items": [
                {"id": 1, "job": {"task": "task1"}},
                {"id": 2, "job": {"task": "task2"}},
                {"id": 3, "job": {"task": "task3"}},
            ],
        }
        self.dynamic_client.resources.get.return_value.get.return_value = mock_response
        queryset = CustomModel.objects.using(self.client).filter(task="task3")
        self.assertEqual(len(queryset), 1)
        self.assertEqual(queryset[0].task, "task3")
        queryset = CustomModel.objects.using(self.client).filter(
            task__in=["task1", "task3"]
        )
        self.assertEqual(len(queryset), 2)
        self.assertEqual(queryset[0].task, "task1")
        self.assertEqual(queryset[1].task, "task3")

    def test_custom_lookup(self):
        mock_response = mock.Mock()
        mock_response.to_dict.side_effect = lambda: {
            "metadata": {},
            "items": [{"id": 1, "job": {"task": "task1"}}],
        }
        self.dynamic_client.resources.get.return_value.get.return_value = mock_response
        queryset = CustomModel.objects.using(self.client).filter(task__foo="task3")
        self.assertEqual(len(queryset), 1)

    def test_contains(self):
        mock_response = mock.Mock()
        mock_response.to_dict.side_effect = lambda: {
            "metadata": {},
            "items": [
                {"id": 1, "job": {"task": "foo"}},
                {"id": 2, "job": {"task": "bar"}},
                {"id": 3, "job": {"task": "barfoobar"}},
            ],
        }
        self.dynamic_client.resources.get.return_value.get.return_value = mock_response
        queryset = CustomModel.objects.using(self.client).filter(task__contains="foo")
        self.assertEqual(len(queryset), 2)

    def test_contains_list(self):
        mock_response = mock.Mock()
        mock_response.to_dict.side_effect = lambda: {
            "metadata": {},
            "items": [
                {"id": 1, "job": {"task": ["foo"]}},
                {"id": 2, "job": {"task": ["foo", "bar"]}},
                {"id": 3, "job": {"task": ["foo", "bar", "new"]}},
            ],
        }
        self.dynamic_client.resources.get.return_value.get.return_value = mock_response
        queryset = CustomModel.objects.using(self.client).filter(
            task__contains=["foo", "new"]
        )
        self.assertEqual(len(queryset), 1)
        self.assertEqual(queryset[0].task, ["foo", "bar", "new"])

    def test_startswith(self):
        mock_response = mock.Mock()
        mock_response.to_dict.side_effect = lambda: {
            "metadata": {},
            "items": [
                {"id": 1, "job": {"task": "foofoo"}},
                {"id": 2, "job": {"task": "fobar"}},
                {"id": 3, "job": {"task": "barfoobar"}},
            ],
        }
        self.dynamic_client.resources.get.return_value.get.return_value = mock_response
        queryset = CustomModel.objects.using(self.client).filter(task__startswith="foo")
        self.assertEqual(len(queryset), 1)

    def test_compare(self):
        mock_response = mock.Mock()
        mock_response.to_dict.side_effect = lambda: {
            "metadata": {},
            "items": [
                {"id": 1, "job": {"task": "foofoo"}},
                {"id": 2, "job": {"task": "fobar"}},
                {"id": 3, "job": {"task": "barfoobar"}},
            ],
        }
        self.dynamic_client.resources.get.return_value.get.return_value = mock_response
        queryset = CustomModel.objects.using(self.client).filter(id__gt=1)
        self.assertEqual(len(queryset), 2)
        queryset = CustomModel.objects.using(self.client).filter(id__gt=2)
        self.assertEqual(len(queryset), 1)
        queryset = CustomModel.objects.using(self.client).filter(id__gte=2)
        self.assertEqual(len(queryset), 2)
        queryset = CustomModel.objects.using(self.client).filter(id__lt=4)
        self.assertEqual(len(queryset), 3)
        queryset = CustomModel.objects.using(self.client).filter(id__lt=1)
        self.assertEqual(len(queryset), 0)
        queryset = CustomModel.objects.using(self.client).filter(id__lte=1)
        self.assertEqual(len(queryset), 1)


class Step:
    parent = None
    client = None


class GetSpec(Step):
    parent = mock.call.resources

    def __init__(self, api_version, kind, inherit=False):
        self.api_version = api_version
        self.kind = kind
        self.inherit = inherit

    @property
    def call(self):
        return self.parent.get(api_version=self.api_version, kind=self.kind)


class GetResource(Step):
    parent = mock.call.resources.get()

    def __init__(self, name, namespace, inherit=False, limit=False):
        self.name = name
        self.namespace = namespace
        self.inherit = inherit
        self.limit = limit

    @property
    def call(self):
        params = {'name': self.name, 'namespace': self.namespace}
        if self.limit:
            params['_continue'] = None
            params['limit'] = 100

        return self.parent.get(**params)


class CreateResource(Step):
    parent = mock.call.resources.get()

    def __init__(
        self,
        template,
        variable,
        namespace="default",
        inherit=False,
        internal=False,
        dry_run=False,
    ):
        self.template = template
        self.variable = variable
        self.namespace = namespace
        self.inherit = inherit
        self.internal = internal
        self.dry_run = dry_run

    @property
    def call(self):
        loader = FileSystemLoader("./tests")
        engine = jinja.JinjaEngine(self.client, loader=loader, internal=self.internal)
        template_backend = backend.TemplateBackend()
        template_backend.set_engine(engine)

        body = template_backend.render(
            self.namespace, self.template, self.variable, self.internal
        )
        params = {"body": body, "namespace": self.namespace}
        if self.dry_run:
            params["query_params"] = [("dryRun", "All")]
        return self.parent.create(**params)


class UpdateResource(Step):
    parent = mock.call.resources.get()

    def __init__(
        self,
        template,
        variable,
        namespace="default",
        inherit=False,
        internal=False,
        dry_run=False,
        resource_version=None
    ):
        self.template = template
        self.variable = variable
        self.namespace = namespace
        self.inherit = inherit
        self.internal = internal
        self.dry_run = dry_run
        self.resource_version = resource_version

    @property
    def call(self):
        loader = FileSystemLoader("./tests")
        engine = jinja.JinjaEngine(self.client, loader=loader, internal=self.internal)
        template_backend = backend.TemplateBackend()
        template_backend.set_engine(engine)

        body = template_backend.render(
            self.namespace, self.template, self.variable, self.internal
        )
        body["metadata"]["resourceVersion"] = self.resource_version
        params = {"body": body, "namespace": self.namespace}
        params["query_params"] = []
        if self.dry_run:
            params["query_params"] = [("dryRun", "All")]
        return self.parent.replace(**params)


class DeleteResource(Step):
    parent = mock.call.resources.get()

    def __init__(self, name, namespace, inherit=False):
        self.name = name
        self.namespace = namespace
        self.inherit = inherit

    @property
    def call(self):
        return self.parent.delete(self.name, self.namespace)


class ToDict(Step):
    parent = mock.call.resources.get().create()

    def __init__(self, inherit=False):
        self.inherit = inherit

    @property
    def call(self):
        return self.parent.to_dict()


class ResourceCreateTestCase(BaseCase):
    def assertQuery(self, steps, query):
        expected_calls = []
        for step in steps:
            step.client = self.client
            if step.inherit:
                step.parent = expected_calls[-1]
            expected_calls.append(step.call)
        query()
        self.assertSequenceEqual(self.dynamic_client.mock_calls, expected_calls)

    def test_create_deployment(self):
        mock_response = {
            "metadata": {
                "name": "foobar",
                "namespace": "default",
                "annotations": {"pharos.py/template": "test.yaml"},
            }
        }
        self.dynamic_client.resources.get.return_value.create.return_value.to_dict.return_value = (
            mock_response
        )

        expected_steps = [
            GetSpec("v1", "Deployment"),
            CreateResource("test.yaml", {"label_name": "foo"}, inherit=True),
            ToDict(inherit=True),
            GetSpec("apiextensions.k8s.io/v1", "CustomResourceDefinition"),
            CreateResource("variable_crd.yaml", {}, inherit=True, internal=True),
            ToDict(inherit=True),
            GetSpec("pharos.py/v1", "Variable"),
            CreateResource(
                "variables.yaml",
                {"name": "deployment-foobar-default", "value": {"label_name": "foo"}},
                inherit=True,
                internal=True,
            ),
            ToDict(inherit=True),
        ]
        query = lambda: models.Deployment.objects.using(self.client).create(
            "test.yaml", {"label_name": "foo"}
        )
        self.assertQuery(expected_steps, query)

    def test_create_deployment_namespace(self):
        mock_response = {
            "metadata": {
                "name": "foobar",
                "namespace": "test",
                "annotations": {"pharos.py/template": "test.yaml"},
            }
        }
        self.dynamic_client.resources.get.return_value.create.return_value.to_dict.return_value = (
            mock_response
        )

        expected_steps = [
            GetSpec("v1", "Deployment"),
            CreateResource(
                "test.yaml", {"label_name": "foo"}, inherit=True, namespace="test"
            ),
            ToDict(inherit=True),
            GetSpec("apiextensions.k8s.io/v1", "CustomResourceDefinition"),
            CreateResource("variable_crd.yaml", {}, inherit=True, internal=True),
            ToDict(inherit=True),
            GetSpec("pharos.py/v1", "Variable"),
            CreateResource(
                "variables.yaml",
                {"name": "deployment-foobar-test", "value": {"label_name": "foo"}},
                inherit=True,
                internal=True,
                namespace="test",
            ),
            ToDict(inherit=True),
        ]
        query = lambda: models.Deployment.objects.using(self.client).create(
            "test.yaml", {"label_name": "foo"}, namespace="test"
        )

        self.assertQuery(expected_steps, query)

    def test_create_deployment_dry(self):
        mock_response = {
            "metadata": {
                "name": "foobar",
                "namespace": "default",
                "annotations": {"pharos.py/template": "test.yaml"},
            }
        }
        self.dynamic_client.resources.get.return_value.create.return_value.to_dict.return_value = (
            mock_response
        )

        expected_steps = [
            GetSpec("v1", "Deployment"),
            CreateResource(
                "test.yaml", {"label_name": "foo"}, inherit=True, dry_run=True
            ),
            ToDict(inherit=True),
        ]
        query = lambda: models.Deployment.objects.using(self.client).create(
            "test.yaml", {"label_name": "foo"}, dry_run=True
        )
        self.assertQuery(expected_steps, query)


class ResourceUpdateTestCase(BaseCase):
    def assertQuery(self, steps, query):
        expected_calls = []
        for step in steps:
            step.client = self.client
            if step.inherit:
                step.parent = expected_calls[-1]
            expected_calls.append(step.call)
        query()
        self.assertSequenceEqual(self.dynamic_client.mock_calls, expected_calls)

    def test_sync_deployment(self):
        mock_response = {
            "metadata": {
                "name": "foobar",
                "namespace": "default",
                "annotations": {"pharos.py/template": "test.yaml"},
            }
        }
        self.dynamic_client.resources.get.return_value.create.return_value.to_dict.return_value = (
            mock_response
        )
        self.dynamic_client.resources.get.return_value.replace.return_value.to_dict.return_value = (
            mock_response
        )

        deployment = models.Deployment(
            client=self.client,
            k8s_object={
                "metadata": {
                    "name": "nginx-deployment",
                    "annotations": {
                        "deployment.kubernetes.io/revision": "1",
                    },
                    "spec": {"selector": {"matchLabels": {"app": "test"}}},
                }
            },
        )
        query = lambda: deployment.sync("test.yaml", {"label_name": "foo"})

        expected_steps = [
            GetSpec("v1", "Deployment"),
            GetResource('nginx-deployment', 'default', inherit=True),
            ToDict(inherit=True),
            GetSpec("v1", "Deployment"),
            UpdateResource(
                "test.yaml", {"label_name": "foo"}, inherit=True
            ),
            ToDict(inherit=True),
            GetSpec("apiextensions.k8s.io/v1", "CustomResourceDefinition"),
            CreateResource("variable_crd.yaml", {}, inherit=True, internal=True),
            ToDict(inherit=True),
            GetSpec("pharos.py/v1", "Variable"),
            DeleteResource('deployment-foobar-default', None),
            GetSpec("pharos.py/v1", "Variable"),
            CreateResource(
                "variables.yaml",
                {"name": "deployment-foobar-default", "value": {"label_name": "foo"}},
                inherit=True,
                internal=True,
            ),
            ToDict(inherit=True),
        ]
        self.assertQuery(expected_steps, query)

    def test_update_deployment(self):
        mock_response = {
            "metadata": {
                "name": "nginx-deployment",
                "namespace": "default",
                "annotations": {"pharos.py/template": "test.yaml"},
            },
            "json": {"label_name": "foo"},
        }
        self.dynamic_client.resources.get.return_value.get.return_value.to_dict.return_value = (
            mock_response
        )
        self.dynamic_client.resources.get.return_value.replace.return_value.to_dict.return_value = (
            mock_response
        )

        deployment = models.Deployment(
            client=self.client,
            k8s_object={
                "metadata": {
                    "name": "nginx-deployment",
                    "annotations": {
                        "deployment.kubernetes.io/revision": "1",
                        "pharos.py/template": "test.yaml",
                        "pharos.py/variable": "deployment-nginx-deployment-default",
                    },
                    "spec": {"selector": {"matchLabels": {"app": "test"}}},
                }
            },
        )
        query = lambda: deployment.deploy()
        expected_steps = [
            GetSpec("v1", "Deployment"),
            GetResource('nginx-deployment', 'default', inherit=True),
            ToDict(inherit=True),
            GetSpec("pharos.py/v1", "Variable"),
            GetResource('deployment-nginx-deployment-default', 'default', inherit=True, limit=True),
            ToDict(inherit=True),
            GetSpec("v1", "Deployment"),
            UpdateResource(
                "test.yaml", {"label_name": "foo"}, inherit=True
            ),
            ToDict(inherit=True),
            GetSpec("pharos.py/v1", "Variable"),
            UpdateResource(
                "variables.yaml",
                {"name": "deployment-nginx-deployment-default", "value": {"label_name": "foo"}},
                namespace='default',
                inherit=True,
                internal=True,
            ),
            ToDict(inherit=True)
        ]
        self.assertQuery(expected_steps, query)

    def test_update_deployment_dry(self):
        mock_response = {
            "metadata": {
                "name": "nginx-deployment",
                "namespace": "default",
                "annotations": {"pharos.py/template": "test.yaml"},
            },
            "json": {"label_name": "foo"},
        }
        self.dynamic_client.resources.get.return_value.get.return_value.to_dict.return_value = (
            mock_response
        )
        self.dynamic_client.resources.get.return_value.replace.return_value.to_dict.return_value = (
            mock_response
        )

        deployment = models.Deployment(
            client=self.client,
            k8s_object={
                "metadata": {
                    "name": "nginx-deployment",
                    "annotations": {
                        "deployment.kubernetes.io/revision": "1",
                        "pharos.py/template": "test.yaml",
                        "pharos.py/variable": "deployment-nginx-deployment-default",
                    },
                    "spec": {"selector": {"matchLabels": {"app": "test"}}},
                }
            },
        )
        query = lambda: deployment.deploy(dry_run=True)
        expected_steps = [
            GetSpec("v1", "Deployment"),
            GetResource('nginx-deployment', 'default', inherit=True),
            ToDict(inherit=True),
            GetSpec("pharos.py/v1", "Variable"),
            GetResource('deployment-nginx-deployment-default', 'default', inherit=True, limit=True),
            ToDict(inherit=True),
            GetSpec("v1", "Deployment"),
            UpdateResource(
                "test.yaml", {"label_name": "foo"}, inherit=True, dry_run=True
            ),
            ToDict(inherit=True),
        ]
        self.assertQuery(expected_steps, query)

    def test_update_deployment_variable(self):
        mock_response = {
            "metadata": {
                "name": "nginx-deployment",
                "namespace": "default",
                "annotations": {"pharos.py/template": "test.yaml"},
            },
            "json": {"label_name": "foo"},
        }
        self.dynamic_client.resources.get.return_value.get.return_value.to_dict.return_value = (
            mock_response
        )
        self.dynamic_client.resources.get.return_value.replace.return_value.to_dict.return_value = (
            mock_response
        )

        deployment = models.Deployment(
            client=self.client,
            k8s_object={
                "metadata": {
                    "name": "nginx-deployment",
                    "annotations": {
                        "deployment.kubernetes.io/revision": "1",
                        "pharos.py/template": "test.yaml",
                        "pharos.py/variable": "deployment-nginx-deployment-default",
                    },
                    "spec": {"selector": {"matchLabels": {"app": "test"}}},
                }
            },
        )

        deployment.set_variable({"label_name": "bar"})
        query = lambda: deployment.deploy()
        expected_steps = [
            GetSpec("v1", "Deployment"),
            GetResource('nginx-deployment', 'default', inherit=True),
            ToDict(inherit=True),
            GetSpec("pharos.py/v1", "Variable"),
            GetResource('deployment-nginx-deployment-default', 'default', inherit=True, limit=True),
            ToDict(inherit=True),
            GetSpec("v1", "Deployment"),
            UpdateResource(
                "test.yaml", {"label_name": "bar"}, inherit=True
            ),
            ToDict(inherit=True),
            GetSpec("pharos.py/v1", "Variable"),
            UpdateResource(
                "variables.yaml",
                {"name": "deployment-nginx-deployment-default", "value": {"label_name": "bar"}},
                namespace='default',
                inherit=True,
                internal=True,
            ),
            ToDict(inherit=True)
        ]
        self.assertQuery(expected_steps, query)
