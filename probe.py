import asyncio
from semantic_kernel import Kernel
from semantic_kernel.functions import kernel_function, KernelArguments
from semantic_kernel.functions.kernel_function import KernelFunction
from semantic_kernel.functions.function_result import FunctionResult
from semantic_kernel.filters.filter_context_base import FilterContextBase
from semantic_kernel.filters.functions.function_invocation_context import FunctionInvocationContext

# Pydantic 2.13+ forward reference compatibility fix for Semantic Kernel 1.47.0
_ns = {
    'Kernel': Kernel,
    'KernelFunction': KernelFunction,
    'KernelArguments': KernelArguments,
    'FunctionResult': FunctionResult,
}
FilterContextBase.model_rebuild(_types_namespace=_ns)
FunctionInvocationContext.model_rebuild(_types_namespace=_ns)

class TestPlugin:
    @kernel_function(name="add", description="Add numbers")
    def add(self, a: float, b: float) -> float:
        print("add method called!", flush=True)
        return float(a) + float(b)

k = Kernel()
plugin = k.add_plugin(TestPlugin(), plugin_name="math")
func = plugin["add"]
print("Type of func:", type(func), flush=True)

async def test_call():
    print("Direct invoke on func...", flush=True)
    res = await func.invoke(k, KernelArguments(a=3.0, b=4.0))
    print("Direct func invoke result:", res.value, flush=True)

asyncio.run(test_call())
