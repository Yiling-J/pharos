from unittest import TestCase, mock
from pharos import models, fields, exceptions, lookups


class BaseCase(TestCase):
    def setUp(self):
        self.dynamic_client = mock.Mock()
        self.client = mock.Mock()
        self.client.settings.enable_chunk = True
        self.client.settings.chunk_size = 100
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


class CustomLookup(lookups.Lookup):
    name = "foo"
    type = lookups.Lookup.POST

    def validate(self, obj, data):
        return True


fields.JsonPathField.add_lookup(CustomLookup)


class CustomModel(models.K8sModel):
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
