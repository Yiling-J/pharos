from unittest import TestCase, mock
from jinja2 import PackageLoader
from kubernetes.dynamic import exceptions as api_exceptions
from pharos import models, fields, exceptions, lookups


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
        deployment = models.Deployment.objects.using(self.client).create(
            "test.yaml", {"label_name": "foo"}
        )
        self.assertEqual(deployment.template, "test.yaml")
        self.assertSequenceEqual(
            self.dynamic_client.resources.method_calls,
            [
                mock.call.get(api_version="v1", kind="Deployment"),
                mock.call.get(
                    api_version="apiextensions.k8s.io/v1",
                    kind="CustomResourceDefinition",
                ),
                mock.call.get(api_version="pharos.py/v1", kind="Variable"),
            ],
        )
        self.assertSequenceEqual(
            self.dynamic_client.resources.get.return_value.method_calls,
            [
                mock.call.create(
                    body={
                        "apiVersion": "apps/v1",
                        "kind": "Deployment",
                        "metadata": {
                            "name": "nginx-deployment",
                            "labels": {"app": "nginx", "foo": "label"},
                            "annotations": {
                                "pharos.py/template": "test.yaml",
                                "pharos.py/variable": "deployment-nginx-deployment-default",
                            },
                        },
                        "spec": {
                            "replicas": 3,
                            "selector": {"matchLabels": {"app": "nginx"}},
                            "template": {
                                "metadata": {"labels": {"app": "nginx"}},
                                "spec": {
                                    "containers": [
                                        {
                                            "name": "nginx",
                                            "image": "nginx:1.14.2",
                                            "ports": [{"containerPort": 80}],
                                        }
                                    ]
                                },
                            },
                        },
                    },
                    namespace="default",
                ),
                mock.call.create(
                    body={
                        "apiVersion": "apiextensions.k8s.io/v1",
                        "kind": "CustomResourceDefinition",
                        "metadata": {"name": "variables.pharos.py"},
                        "spec": {
                            "group": "pharos.py",
                            "names": {
                                "kind": "Variable",
                                "plural": "variables",
                                "singular": "variable",
                            },
                            "scope": "Cluster",
                            "versions": [
                                {
                                    "name": "v1",
                                    "schema": {
                                        "openAPIV3Schema": {
                                            "properties": {
                                                "json": {
                                                    "x-kubernetes-preserve-unknown-fields": True,
                                                    "type": "object",
                                                }
                                            },
                                            "type": "object",
                                        }
                                    },
                                    "served": True,
                                    "storage": True,
                                }
                            ],
                        },
                    },
                    namespace="default",
                ),
                mock.call.create(
                    body={
                        "apiVersion": "pharos.py/v1",
                        "kind": "Variable",
                        "metadata": {"name": "deployment-foobar-default"},
                        "json": {"label_name": "foo"},
                    },
                    namespace="default",
                ),
            ],
        )

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
        deployment = models.Deployment.objects.using(self.client).create(
            "test.yaml", {"label_name": "foo"}, namespace="test"
        )
        self.assertEqual(deployment.template, "test.yaml")
        self.assertSequenceEqual(
            self.dynamic_client.resources.method_calls,
            [
                mock.call.get(api_version="v1", kind="Deployment"),
                mock.call.get(
                    api_version="apiextensions.k8s.io/v1",
                    kind="CustomResourceDefinition",
                ),
                mock.call.get(api_version="pharos.py/v1", kind="Variable"),
            ],
        )
        self.assertSequenceEqual(
            self.dynamic_client.resources.get.return_value.method_calls,
            [
                mock.call.create(
                    body={
                        "apiVersion": "apps/v1",
                        "kind": "Deployment",
                        "metadata": {
                            "name": "nginx-deployment",
                            "labels": {"app": "nginx", "foo": "label"},
                            "annotations": {
                                "pharos.py/template": "test.yaml",
                                "pharos.py/variable": "deployment-nginx-deployment-test",
                            },
                        },
                        "spec": {
                            "replicas": 3,
                            "selector": {"matchLabels": {"app": "nginx"}},
                            "template": {
                                "metadata": {"labels": {"app": "nginx"}},
                                "spec": {
                                    "containers": [
                                        {
                                            "name": "nginx",
                                            "image": "nginx:1.14.2",
                                            "ports": [{"containerPort": 80}],
                                        }
                                    ]
                                },
                            },
                        },
                    },
                    namespace="test",
                ),
                mock.call.create(
                    body={
                        "apiVersion": "apiextensions.k8s.io/v1",
                        "kind": "CustomResourceDefinition",
                        "metadata": {"name": "variables.pharos.py"},
                        "spec": {
                            "group": "pharos.py",
                            "names": {
                                "kind": "Variable",
                                "plural": "variables",
                                "singular": "variable",
                            },
                            "scope": "Cluster",
                            "versions": [
                                {
                                    "name": "v1",
                                    "schema": {
                                        "openAPIV3Schema": {
                                            "properties": {
                                                "json": {
                                                    "x-kubernetes-preserve-unknown-fields": True,
                                                    "type": "object",
                                                }
                                            },
                                            "type": "object",
                                        }
                                    },
                                    "served": True,
                                    "storage": True,
                                }
                            ],
                        },
                    },
                    namespace="default",
                ),
                mock.call.create(
                    body={
                        "apiVersion": "pharos.py/v1",
                        "kind": "Variable",
                        "metadata": {"name": "deployment-foobar-test"},
                        "json": {"label_name": "foo"},
                    },
                    namespace="test",
                ),
            ],
        )

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
        deployment = models.Deployment.objects.using(self.client).create(
            "test.yaml", {"label_name": "foo"}, dry_run=True
        )
        self.assertEqual(deployment.template, "test.yaml")
        self.assertSequenceEqual(
            self.dynamic_client.resources.method_calls,
            [
                mock.call.get(api_version="v1", kind="Deployment"),
            ],
        )
        self.assertSequenceEqual(
            self.dynamic_client.resources.get.return_value.method_calls,
            [
                mock.call.create(
                    body={
                        "apiVersion": "apps/v1",
                        "kind": "Deployment",
                        "metadata": {
                            "name": "nginx-deployment",
                            "labels": {"app": "nginx", "foo": "label"},
                            "annotations": {
                                "pharos.py/template": "test.yaml",
                                "pharos.py/variable": "deployment-nginx-deployment-default",
                            },
                        },
                        "spec": {
                            "replicas": 3,
                            "selector": {"matchLabels": {"app": "nginx"}},
                            "template": {
                                "metadata": {"labels": {"app": "nginx"}},
                                "spec": {
                                    "containers": [
                                        {
                                            "name": "nginx",
                                            "image": "nginx:1.14.2",
                                            "ports": [{"containerPort": 80}],
                                        }
                                    ]
                                },
                            },
                        },
                    },
                    namespace="default",
                    query_params=[("dryRun", "All")],
                ),
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
        deployment.deploy()
        self.assertSequenceEqual(
            self.dynamic_client.resources.method_calls,
            [
                mock.call.get(api_version="v1", kind="Deployment"),
                mock.call.get(api_version="pharos.py/v1", kind="Variable"),
                mock.call.get(api_version="v1", kind="Deployment"),
                mock.call.get(api_version="pharos.py/v1", kind="Variable"),
            ],
        )
        self.assertSequenceEqual(
            self.dynamic_client.resources.get.return_value.method_calls,
            [
                mock.call.get(name="nginx-deployment", namespace="default"),
                mock.call.get(
                    _continue=None,
                    limit=100,
                    name="deployment-nginx-deployment-default",
                ),
                mock.call.replace(
                    body={
                        "apiVersion": "apps/v1",
                        "kind": "Deployment",
                        "metadata": {
                            "name": "nginx-deployment",
                            "labels": {"app": "nginx", "foo": "label"},
                            "annotations": {
                                "pharos.py/template": "test.yaml",
                                "pharos.py/variable": "deployment-nginx-deployment-default",
                            },
                            "resourceVersion": None,
                        },
                        "spec": {
                            "replicas": 3,
                            "selector": {"matchLabels": {"app": "nginx"}},
                            "template": {
                                "metadata": {"labels": {"app": "nginx"}},
                                "spec": {
                                    "containers": [
                                        {
                                            "name": "nginx",
                                            "image": "nginx:1.14.2",
                                            "ports": [{"containerPort": 80}],
                                        }
                                    ]
                                },
                            },
                        },
                    },
                    namespace="default",
                    query_params=[],
                ),
                mock.call.replace(
                    body={
                        "apiVersion": "pharos.py/v1",
                        "kind": "Variable",
                        "metadata": {
                            "name": "deployment-nginx-deployment-default",
                            "resourceVersion": None,
                        },
                        "json": {"label_name": "foo"},
                    },
                    namespace="default",
                    query_params=[],
                ),
            ],
        )

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
        deployment.deploy(dry_run=True)
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
                mock.call.get(
                    _continue=None,
                    limit=100,
                    name="deployment-nginx-deployment-default",
                ),
                mock.call.replace(
                    body={
                        "apiVersion": "apps/v1",
                        "kind": "Deployment",
                        "metadata": {
                            "name": "nginx-deployment",
                            "labels": {"app": "nginx", "foo": "label"},
                            "annotations": {
                                "pharos.py/template": "test.yaml",
                                "pharos.py/variable": "deployment-nginx-deployment-default",
                            },
                            "resourceVersion": None,
                        },
                        "spec": {
                            "replicas": 3,
                            "selector": {"matchLabels": {"app": "nginx"}},
                            "template": {
                                "metadata": {"labels": {"app": "nginx"}},
                                "spec": {
                                    "containers": [
                                        {
                                            "name": "nginx",
                                            "image": "nginx:1.14.2",
                                            "ports": [{"containerPort": 80}],
                                        }
                                    ]
                                },
                            },
                        },
                    },
                    namespace="default",
                    query_params=[("dryRun", "All")],
                ),
            ],
        )

    def test_update_deployment_variale(self):
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
        deployment.deploy()
        self.assertSequenceEqual(
            self.dynamic_client.resources.method_calls,
            [
                mock.call.get(api_version="v1", kind="Deployment"),
                mock.call.get(api_version="pharos.py/v1", kind="Variable"),
                mock.call.get(api_version="v1", kind="Deployment"),
                mock.call.get(api_version="pharos.py/v1", kind="Variable"),
            ],
        )
        self.assertSequenceEqual(
            self.dynamic_client.resources.get.return_value.method_calls,
            [
                mock.call.get(name="nginx-deployment", namespace="default"),
                mock.call.get(
                    _continue=None,
                    limit=100,
                    name="deployment-nginx-deployment-default",
                ),
                mock.call.replace(
                    body={
                        "apiVersion": "apps/v1",
                        "kind": "Deployment",
                        "metadata": {
                            "name": "nginx-deployment",
                            "labels": {"app": "nginx", "bar": "label"},
                            "annotations": {
                                "pharos.py/template": "test.yaml",
                                "pharos.py/variable": "deployment-nginx-deployment-default",
                            },
                            "resourceVersion": None,
                        },
                        "spec": {
                            "replicas": 3,
                            "selector": {"matchLabels": {"app": "nginx"}},
                            "template": {
                                "metadata": {"labels": {"app": "nginx"}},
                                "spec": {
                                    "containers": [
                                        {
                                            "name": "nginx",
                                            "image": "nginx:1.14.2",
                                            "ports": [{"containerPort": 80}],
                                        }
                                    ]
                                },
                            },
                        },
                    },
                    namespace="default",
                    query_params=[],
                ),
                mock.call.replace(
                    body={
                        "apiVersion": "pharos.py/v1",
                        "kind": "Variable",
                        "metadata": {
                            "name": "deployment-nginx-deployment-default",
                            "resourceVersion": None,
                        },
                        "json": {"label_name": "bar"},
                    },
                    namespace="default",
                    query_params=[],
                ),
            ],
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
            [mock.call.get(_continue=None, label_selector="foo=bar", limit=100)],
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
