import pytest
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

class MathPlugin:
    @kernel_function(name="multiply", description="Multiply two numbers")
    def multiply(self, x: float, y: float) -> float:
        return float(x) * float(y)

@pytest.mark.asyncio
async def test_sk_plugin_invocation():
    kernel = Kernel()
    plugin = kernel.add_plugin(MathPlugin(), plugin_name="Math")
    assert "multiply" in plugin.functions
    
    func = plugin["multiply"]
    result = await kernel.invoke(func, KernelArguments(x=6.0, y=7.0))
    assert float(result.value) == 42.0
