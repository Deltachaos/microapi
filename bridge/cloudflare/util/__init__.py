from js import Object
from pyodide.ffi import to_js as _to_js, JsProxy

def to_js(obj):
    return _to_js(obj, dict_converter=Object.fromEntries)

def to_py(obj):
    if not isinstance(obj, JsProxy):
        return obj
    return obj.to_py()
