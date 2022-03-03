class SafeAttributeObject:
    def __init__(self, obj):
        self.obj = obj

    def __getattr__(self, item):
        try:
            return getattr(self.obj, item)
        except AttributeError:
            return None


def update_obj(obj, data):
    for field, value in data.items():
        setattr(obj, field, value)
    obj.save()
    return obj
