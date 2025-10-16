import ast
import inspect
from typing import Any, Callable, Coroutine, Dict, List, Union


class ExpressionEvaluator(ast.NodeTransformer):
    def __init__(self, providers: List[object]):
        self.functions: Dict[str, Callable[..., Coroutine]] = {}
        for provider in providers:
            for attr in dir(provider):
                func = getattr(provider, attr)
                if inspect.iscoroutinefunction(func):
                    self.functions[attr] = func

    async def eval(self, expression: str) -> Any:
        tree = ast.parse(expression, mode="eval")
        compiled = await self._eval_ast(tree.body)
        return compiled

    async def _eval_ast(self, node):
        if isinstance(node, ast.Call):
            func_name = self._get_func_name(node.func)
            if func_name not in self.functions:
                raise NameError(f"Function {func_name} not found.")
            args = [await self._eval_ast(arg) for arg in node.args]
            return await self.functions[func_name](*args)

        elif isinstance(node, ast.BinOp):
            left = await self._eval_ast(node.left)
            right = await self._eval_ast(node.right)
            return self._eval_op(node.op, left, right)

        elif isinstance(node, ast.BoolOp):
            values = [await self._eval_ast(v) for v in node.values]
            if isinstance(node.op, ast.Or):
                return any(values)
            elif isinstance(node.op, ast.And):
                return all(values)

        elif isinstance(node, ast.UnaryOp):
            operand = await self._eval_ast(node.operand)
            if isinstance(node.op, ast.Not):
                return not operand
            elif isinstance(node.op, ast.USub):
                return -operand

        elif isinstance(node, ast.Compare):
            left = await self._eval_ast(node.left)
            results = []
            for op, comparator in zip(node.ops, node.comparators):
                right = await self._eval_ast(comparator)
                results.append(self._eval_cmp(op, left, right))
                left = right
            return all(results)

        elif isinstance(node, ast.IfExp):
            test = await self._eval_ast(node.test)
            if test:
                return await self._eval_ast(node.body)
            else:
                return await self._eval_ast(node.orelse)

        elif isinstance(node, ast.Attribute):
            value = await self._eval_ast(node.value)
            return getattr(value, node.attr)

        elif isinstance(node, ast.Name):
            # fallback: try calling as a function without arguments
            if node.id in self.functions:
                return await self.functions[node.id]()
            raise NameError(f"Name {node.id} is not defined.")

        elif isinstance(node, ast.Constant):
            return node.value

        else:
            raise NotImplementedError(f"Unsupported AST node: {ast.dump(node)}")

    def _get_func_name(self, func_node: ast.AST) -> str:
        if isinstance(func_node, ast.Name):
            return func_node.id
        raise NotImplementedError(f"Unsupported func node: {ast.dump(func_node)}")

    def _eval_op(self, op, left, right):
        if isinstance(op, ast.Add): return left + right
        if isinstance(op, ast.Sub): return left - right
        if isinstance(op, ast.Mult): return left * right
        if isinstance(op, ast.Div): return left / right
        if isinstance(op, ast.Mod): return left % right
        raise NotImplementedError(f"Operator {op} not supported")

    def _eval_cmp(self, op, left, right):
        if isinstance(op, ast.Eq): return left == right
        if isinstance(op, ast.NotEq): return left != right
        if isinstance(op, ast.Lt): return left < right
        if isinstance(op, ast.LtE): return left <= right
        if isinstance(op, ast.Gt): return left > right
        if isinstance(op, ast.GtE): return left >= right
        raise NotImplementedError(f"Comparison {op} not supported")


class FunctionProvider:
    pass
