# Pharos

![Workflow](https://github.com/Yiling-J/pharos/actions/workflows/main.yaml/badge.svg)

Managing Kubernetes resources in Python.


## Installation

```
pip install pharos-k8s
```

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

Pharos default settings

```python
{
    "disable_compress": False,  # disable gzip
    "enable_chunk": True,  # enable chunk
    "chunk_size": 200,  # chunk size
    "template_engine": "pharos.jinja.JinjaEngine",  # templating engine
    "jinja_loader": None,  # loader for Jinja template
}

```

If you enable [chunk](https://kubernetes.io/docs/reference/using-api/api-concepts/#retrieving-large-results-sets-in-chunks), Pharos will use `limit/continue` parameters to retrieve API results in small chunks, avoiding large responses.


#### basic query syntax, follow Django ORM style. See all available resources in models.py

```python
from pharos.models import Deployment
from pharos.client import Client


client = Client('YOUR_PATH/.kube/config')

# filter or get
deployments = Deployment.objects.using(client).filter(namespace='default')
deployment = deployments[0]
deployment = Deployment.objects.using(client).get(name='foo', namespace='default')

# print configuration yaml
print(deployment.yaml)

# print configuration json object
print(deployment.k8s_object)

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

#### custom resource example

create custom resource definition
```python
from pharos.models import CustomResourceDefinition


CustomResourceDefinition.objects.using(client).create('crontab.yaml', {})

```

add model
```python
from pharos.models import Model


class CronTab(Model):

    class Meta:
        api_version = "stable.example.com/v1"
        kind = "CronTab"

```

#### template engine
Pharos using pluggable template engine for resource creating/updating. A template engine means
input an identifier string and a json serializable object, output json k8s configuration.
Then Pharos can use that configuration in creating/updating.
For example, the default template engine is Jinja, so the identifier string would be path to your yaml
template, and json serializable object would be variables used in the template.

Pharos add 2 annotations to your resource automatically, one for identifier and one for variable, in
this way when updating resource, you don't need to repeat the same thing twice.


#### create resource(Jinja example)

```python
from jinja2 import FileSystemLoader
from pharos.models import Deployment
from pharos.client import Client


# jinja_loader settings is required because pharos need to know
# where to find template
client = Client('config', jinja_loader=FileSystemLoader('./templates/'))

# jinja is the default engine, for other template engines
# client = Client('config', template_engine='your_template_engine_class')

# render template and print yaml
Deployment.objects.using(client).render('test.yaml', {'foo': 'bar'})

# here test.yaml is template and {'foo': 'bar'} is variable
deployment = Deployment.objects.using(client).create('test.yaml', {'foo': 'bar'})

# dry run
deployment = Deployment.objects.using(client).create('test.yaml', {'foo': 'bar'}, dry_run=True)

# access template and variable
template = deployment.template
variable = deployment.variable.get()
variable_data = variable.data

```

#### update resource(Jinja example)

```python
from jinja2 import FileSystemLoader
from pharos.models import Deployment
from pharos.client import Client


client = Client('config', jinja_loader=FileSystemLoader('./templates/'))

# template change
deployment = Deployment.objects.using(client).all()[0]
deployment.deploy()

# dry run
deployment.deploy(dry_run=True)

# also change variable
deployment.set_variable({'bar': 'foo'})
deployment.deploy()

```

#### migrate existing resource
migrate will replace existing resource with provided template and variable

```python
from jinja2 import FileSystemLoader
from pharos.models import Deployment
from pharos.client import Client


client = Client('config', jinja_loader=FileSystemLoader('./templates/'))

deployment = Deployment.objects.using(client).all()[0]
deployment.sync('test.yaml', {'foo': 'bar'})

# dry run
deployment.sync('test.yaml', {'foo': 'bar'}, dry_run=True)

```


#### delete resource

```python
from pharos.models import Deployment
from pharos.client import Client


client = Client('YOUR_PATH/.kube/config')

deployment = Deployment.objects.using(client).filter(namespace='default')[0]
deployment.delete()

```
