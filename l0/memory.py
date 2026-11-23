
from .errors import L0Error


class ScopeFrame:
    def __init__(self, parent):
        self.parent = parent
        self.variables = {}
        self.functions = {}
        self.kind = None
        self.slots = []


class Memory:
    def __init__(self, names):
        self.names = list(names)
        self.values = [0] * len(names)
        self.defined = [False] * len(names)
        self.global_frame = ScopeFrame(None)
        self.global_frame.variables = {name: i for i, name in enumerate(names)}
        self.current = self.global_frame
        self.function_frame = None
        self.scopes = []
        self.free_locals = []

    def load(self, slot):
        if not self.defined[slot]:
            raise L0Error('ERROR: variable "%s" is undefined' % self.names[slot])
        return self.values[slot]

    def store(self, slot, value):
        self.values[slot] = value
        self.defined[slot] = True

    def new_local(self, frame, name, value=0, defined=False):
        if self.free_locals:
            slot = self.free_locals.pop()
            self.names[slot] = name
            self.values[slot] = value
            self.defined[slot] = defined
        else:
            slot = len(self.names)
            self.names.append(name)
            self.values.append(value)
            self.defined.append(defined)
        frame.variables[name] = slot
        frame.slots.append(slot)
        return slot

    def slot_of(self, name):
        frame = self.current
        while frame is not None:
            if name in frame.variables:
                return frame.variables[name]
            frame = frame.parent
        if self.function_frame is not None:
            return self.new_local(self.function_frame, name)
        slot = len(self.names)
        self.names.append(name)
        self.values.append(0)
        self.defined.append(False)
        self.global_frame.variables[name] = slot
        return slot

    def push_scope(self, bindings, variables=(), functions=(), parent=None, call=False):
        previous = self.current
        frame = ScopeFrame(previous if parent is None else parent)
        frame.kind = "ARG" if call else "LOC"
        self.scopes.append((previous, self.function_frame, frame))
        self.current = frame
        if call:
            self.function_frame = frame
        for name in variables:
            self.new_local(frame, name)
        for name, value in bindings.items():
            self.new_local(frame, name, value, True)
        for function in functions:
            frame.functions[function.name] = (function, frame)

    def pop_scope(self):
        previous, old_function, frame = self.scopes.pop()
        self.current = previous
        self.function_frame = old_function
        self.free_locals.extend(frame.variables.values())

    def function_of(self, name):
        frame = self.current
        while frame is not None:
            if name in frame.functions:
                return frame.functions[name]
            frame = frame.parent
        raise L0Error('ERROR: function "%s" is undefined' % name)
