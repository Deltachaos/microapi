import js
from js import Object
from pyodide.ffi import to_js as _to_js, JsProxy


def _js_null():
    raise NotImplementedError()

#Object.fromEntries

# https://github.com/pyodide/pyodide/issues/3968
# dict_converter = run_js(
#     """
#     ((entries) => {
#       for(let entry of entries) {
#         if(entry[1] === undefined) {
#           entry[1] = null;
#         }
#       }
#       return Object.fromEntries(entries);
#     })
#     """
# )


def _from_entries_null(entries):
    # TODO handle null case
    return Object.fromEntries(entries)


def to_js(obj, keep_null=False):
    if keep_null:
        if obj is None:
            return _js_null()
        else:
            return _to_js(obj, dict_converter=_from_entries_null)

    return _to_js(obj, dict_converter=Object.fromEntries)


def to_py(obj):
    if not isinstance(obj, JsProxy):
        return obj
    return obj.to_py()
