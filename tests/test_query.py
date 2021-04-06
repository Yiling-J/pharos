from unittest import TestCase, mock
from pharos import models, operators


class BaseCase(TestCase):

    def setUp(self):
        self.client = mock.Mock()


class DeploymentTestCase(BaseCase):
    def test_deployment_query_basic(self):
        test_cases = [
            {
                "query": models.Deployment.objects.using(self.client).all(),
                "api_call": {},
            },
            {
                "query": models.Deployment.objects.using(self.client).filter(name="apple"),
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
        self.client.resources.get.return_value.get.return_value.to_dict.return_value = []
        for case in test_cases:
            with self.subTest(case=case):
                len(case["query"])
                self.assertEqual(
                    self.client.resources.method_calls,
                    [mock.call.get(api_version='v1', kind='Deployment')]
                )
                self.assertEqual(
                    self.client.resources.get.return_value.method_calls,
                    [mock.call.get(**case['api_call'])]
                )
                self.client.reset_mock()

    def test_owner(self):
        mock_data = {"kind": "Apple", "metadata": {"uid": "123"}}
        mock_owner = models.Deployment(client=None, k8s_object=mock_data)

        mock_response = mock.Mock()
        mock_response.to_dict.return_value = {
            "items": [
                {
                    "id": 1,
                    "metadata": {
                        "ownerReferences": [{"kind": "Apple", "uid": "123"}],
                        "name": "test"
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
            ]
        }
        self.client.resources.get.return_value.get.return_value = mock_response
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
        self.assertEqual(deployment.name, 'test')

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
            ]
        }

        mock_pod_response = mock.Mock()
        mock_pod_response.to_dict.return_value = {
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
            ]
        }

        # pod come first because owner filter is POST operator
        self.client.resources.get.return_value.get.side_effect = [
            mock_pod_response,
            mock_rs_response,
        ]

        self.assertEqual(len(deployment.pods.all()), 1)


class CustomModel(models.K8sModel):
    task = models.QueryField(operator=operators.JsonPathOperator, path="job.task")

    class Meta:
        api_version = "v1"
        kind = "CustomModel"


class CustomModelTestCase(TestCase):
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
