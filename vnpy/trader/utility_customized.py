import traceback


def is_self(self):
    for tb in traceback.walk_stack(None):
        caller = tb[0].f_locals.get("self")
        if caller and caller is self:
            print("Execute custom")
            return True
    else:
        print("Skip custom")
        return False


class WrapIt(object):
    def __init__(self, cls, name, func):
        self.cls = cls
        self.name = name
        self.func = func
        self.origin = getattr(cls, name)
        self.origin = self.origin

    def wrap(self):
        def origin(*args, **kwargs):
            self.func(*args, **kwargs)
            return self.origin(*args, **kwargs)

        return origin

    def __enter__(self):
        setattr(self.cls, self.name, self.wrap())
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        setattr(self.cls, self.name, self.origin)
        pass
