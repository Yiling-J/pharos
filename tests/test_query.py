from unittest import TestCase, mock
from pharos import models


@mock.patch('pharos.query.DynamicClient')
class DeploymentTestCase(TestCase):

    def test_deployment_query_basic(self, m):
        test_cases = [
            {
                'query': models.Deployment.objects.using('a').all(),
                'api_call': {'api_version': 'v1', 'kind': 'Deployment'}
            },
            {
                'query': models.Deployment.objects.using('a').filter(name='apple'),
                'api_call': {'api_version': 'v1', 'kind': 'Deployment', 'name': 'apple'}
            },
            {
                'query': models.Deployment.objects.using('a').filter(name='apple', namespace='orange'),
                'api_call': {'api_version': 'v1', 'kind': 'Deployment', 'name': 'apple', 'namespace': 'orange'}
            },
            {
                'query': models.Deployment.objects.using('a').filter(name='apple').filter(namespace='orange'),
                'api_call': {'api_version': 'v1', 'kind': 'Deployment', 'name': 'apple', 'namespace': 'orange'}
            },
            {
                'query': models.Deployment.objects.using('a').filter(selector='app in (a)'),
                'api_call': {'api_version': 'v1', 'kind': 'Deployment', 'label_selector': 'app in (a)'}
            },
            {
                'query': models.Deployment.objects.using('a').filter(selector='app in (a)').filter(selector='app=b'),
                'api_call': {'api_version': 'v1', 'kind': 'Deployment', 'label_selector': 'app in (a),app=b'}
            }
        ]
        for case in test_cases:
            with self.subTest(case=case):
                len(case['query'])
        print(m.return_value.method_calls)

    def test_owner(self, m):
        mock_data = {
            'kind': 'Apple',
            'metadata': {
                'uid': '123'
            }
        }
        mock_owner = models.Deployment(
            client=None,
            k8s_object=mock_data
        )

        mock_response = [
            {'id': 1, 'metadata': {'ownerReferences': [{'kind': 'Apple', 'uid': '123'}]}},
            {'id': 2, 'metadata': {'ownerReferences': [{'kind': 'Appl', 'uid': '1'}]}},
            {'id': 3, 'metadata': {'ownerReferences': [{'kind': 'Apple', 'uid': '12'}]}},
            {'id': 4, 'metadata': {'ownerReferences': [{'kind': 'Apple'}]}},
            {'id': 6, 'metadata': {'ownerReferences': [{'kind': 'Apple', 'uid': '123'}]}}
        ]
        m.return_value.resources.get.return_value = mock_response
        query = models.Deployment.objects.using('a').filter(owner=mock_owner)
        self.assertEqual(len(query), 2)
