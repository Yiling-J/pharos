class ClientNotSet(Exception):
    pass


class FieldDoesNotExist(Exception):
    pass


class ObjectDoesNotExist(Exception):
    pass


class MultipleObjectsReturned(Exception):
    pass


class ValidationError(Exception):
    pass


class OperatorNotValid(Exception):
    pass


class LookupNotValid(Exception):
    pass


class TemplateNotValid(Exception):
    pass


class ResourceNotMatch(Exception):
    pass
