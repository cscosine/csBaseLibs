from csorchestrator.domain.context.context_compiler_generator import (
    Compiler,
    ContextCompilerGenerator,
    GeneratorWithType,
)
from csorchestrator.domain.context.context_os_architecture import OS
from csorchestrator.domain.context.context_os_architecture_compiler_generator import (
    ContextOsArchitectureCompilerGenerator,
)


def qt6_mapping(
    context: ContextOsArchitectureCompilerGenerator,
) -> ContextOsArchitectureCompilerGenerator | None:
    if context.context_os_architecture.os == OS.LINUX:
        newContext = context
        newContext.context_compiler_generator = ContextCompilerGenerator(
            compiler_family=Compiler.GCC,
            compiler_version=ContextCompilerGenerator.COMPILER_VERSION_DEFAULT,
            build_generator=GeneratorWithType.NINJA,
        )
        return newContext
    elif context.context_os_architecture.os == OS.WINDOWS:
        newContext = context
        newContext.context_compiler_generator = ContextCompilerGenerator(
            compiler_family=Compiler.MSVC,
            compiler_version=ContextCompilerGenerator.COMPILER_VERSION_MSVC_2022_17,
            build_generator=GeneratorWithType.NINJA,
        )
        return newContext
    return None
