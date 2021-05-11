# Pharos(WIP)

![Workflow](https://github.com/Yiling-J/pharos/actions/workflows/main.yaml/badge.svg)

Managing Kubernetes resources in Python.


## Example

#### create client

```python
from pharos.client import Client


client = Client('YOUR_PATH/.kube/config')

# if you have multiple context in one config file
client = Client('YOUR_PATH/.kube/config', context='context_name_you_want')

# switch client context
client.use_context('new_context_name')

```

#### create client with settings

```python
from pharos.client import Client


client = Client('YOUR_PATH/.kube/config', disable_compress=True, chunk_size=500)

# access settings
client.settings.chunk_size

```
#### basic query syntax, follow Django ORM style. See all available resources in models.py

```python
from pharos.models import Deployment
from pharos.client import Client


client = Client('YOUR_PATH/.kube/config')

# filter or get
deployments = Deployment.objects.using(client).filter(namespace='default')
deployment = deployments[0]
deployment = Deployment.objects.using(client).get(name='foo', namespace='default')

# get pods owned by deployment, notice that no ```.using(client)``` here
pods = deployment.pods.all()

# select labels, also support chain select
Deployment.objects.using(client).filter(selector='app=test,version=v1')
Deployment.objects.using(client).filter(selector='app=test').filter(selector='version=v1')

# limit results
pods = Pod.objects.all().limit(100)

# various lookups
Deployment.objects.using(client).filter(name__contains='foo')
Deployment.objects.using(client).filter(name__startswith='foo')
Deployment.objects.using(client).filter(name__in=['foo', 'bar'])
Deployment.objects.using(client).filter(replicas__gt=1)
Deployment.objects.using(client).filter(replicas__lt=5)


# refresh query
pods_refreshed = pods.all()

# refresh instance
pod = pods[0]
pod.refresh()

```

#### extend existing model

```python
from pharos.models import Deployment
from pharos.client import Client
from pharos import fields


class MyDeployment(Deployment):
    uid = fields.JsonPathField(path="metadata.uid")
    created = fields.DateTimeField(path="metadata.creationTimestamp")


deployment = MyDeployment.objects.using(client).all()[0]
print(deployment.uid)
print(deployment.created)

# you can use filter and lookups on your fields
MyDeployment.objects.using(client).filter(uid='123')
MyDeployment.objects.using(client).filter(created__gt=datetime(2010, 1, 1, tzinfo=timezone.utc))

```

#### create your own model

```python
from pharos.models import Model


class TestResource(Model):

    class Meta:
        api_version = "v1"
        kind = "TestResource"

```

#### create resource
Pharos using template engine for resource creating/updating. That means to create a resource,
you need prepare 2 things: template and variable. template can be yaml file/python class or
other things, depend on your template engine. Variable must be json serializable object.
Template engine will call `render(template, variable)` to get k8s configuration json.

```python
from jinja2 import FileSystemLoader
from pharos.models import Deployment
from pharos.client import Client


# jinja example, jinja_loader settings is required because pharos need to know
# where to find template
client = Client('config', jinja_loader=FileSystemLoader('./templates/'))


# jinja is the default engine, for other template engines
# client = Client('config', template_engine='your_template_engine_class')


# here test.yaml is template and {'foo': 'bar'} is variable
Deployment.objects.using(client).create('test.yaml', {'foo': 'bar'})


```

#### update resource
After creating resource, Pharos will add 2 annotations to automatically. First is the variable custom
resource name, second is template name. With these info, Pharos can redeploy your resource.

```python
from jinja2 import FileSystemLoader
from pharos.models import Deployment
from pharos.client import Client


client = Client('config', jinja_loader=FileSystemLoader('./templates/'))


# template change
deployment = Deployment.objects.using(client).all()[0]
deployment.deploy()


# also change variable
deployment.set_variable({'bar': 'foo'})
deployment.deploy()

```
