"""fail-closed 参数解析（规范 §5.3）。

核心算法调用前执行 ResolveAll(RequiredParams)；任何参数无法解析来源、
单位未知或缺少证据引用，均直接抛错，禁止用默认值代替。
"""

from __future__ import annotations

from typing import Iterable

from valor.core.errors import (
    ParameterConflictError,
    UnresolvedParameterError,
)

from .models import ParameterManifest, ResolvedParameter


class ParameterResolver:
    """持有已解析参数注册表，提供 fail-closed 查询。

    用法：
        resolver = ParameterResolver()
        resolver.register(alpha_resolved)
        alpha = resolver.require("alpha")   # 缺失即抛 UNRESOLVED_PARAMETER
    """

    def __init__(self, manifest: ParameterManifest | None = None) -> None:
        self._by_name: dict[str, ResolvedParameter] = {}
        if manifest is not None:
            self._by_name.update(manifest.by_name())

    def register(self, param: ResolvedParameter) -> None:
        """注册一个已解析参数。

        若同名参数已存在且来源/单位/值冲突 → 抛 PARAMETER_CONFLICT
        （检查单 Q#20/#21：同名参数来源/unit 冲突必须被拒绝）。
        """
        existing = self._by_name.get(param.name)
        if existing is not None:
            conflicts = []
            if existing.source_kind != param.source_kind:
                conflicts.append(
                    f"来源 {existing.source_kind.value} vs {param.source_kind.value}"
                )
            if existing.unit != param.unit:
                conflicts.append(f"单位 {existing.unit} vs {param.unit}")
            if existing.value != param.value:
                conflicts.append(f"值 {existing.value!r} vs {param.value!r}")
            if conflicts:
                raise ParameterConflictError(
                    f"[{param.name}] 同名参数冲突: " + "; ".join(conflicts)
                )
        self._by_name[param.name] = param

    def register_many(self, params: Iterable[ResolvedParameter]) -> None:
        for p in params:
            self.register(p)

    def require(self, name: str) -> ResolvedParameter:
        """按名取已解析参数；缺失抛 UNRESOLVED_PARAMETER。"""
        p = self._by_name.get(name)
        if p is None:
            raise UnresolvedParameterError(
                f"[{name}] 参数未解析来源（UNRESOLVED_PARAMETER）"
            )
        return p

    def resolve_all(self, names: Iterable[str]) -> dict[str, ResolvedParameter]:
        """批量解析并返回 {name: param}；任一缺失即抛错（ResolveAll Gate）。"""
        result: dict[str, ResolvedParameter] = {}
        for n in names:
            result[n] = self.require(n)
        return result


def require_resolved(name: str) -> ResolvedParameter:
    """模块级便捷函数：从当前上下文解析参数（规范 §5.3 推荐用法）。

    说明：本函数通过 _CONTEXT 读取最近一次显式设置的 ParameterResolver。
    推荐在核心函数内使用显式传入的 resolver.require(name)，更清晰且无隐式全局。
    此处保留该函数以对齐规范 §5.3 的示例写法，并在缺失时同样 fail closed。
    """
    ctx = _CONTEXT.resolver
    if ctx is None:
        raise UnresolvedParameterError(
            f"[{name}] 未设置参数上下文（UNRESOLVED_PARAMETER）"
        )
    return ctx.require(name)


class _ResolverContext:
    """线程无关的解析上下文（模块级）。"""

    def __init__(self) -> None:
        self.resolver: ParameterResolver | None = None


_CONTEXT = _ResolverContext()


def set_resolver_context(resolver: ParameterResolver) -> ParameterResolver:
    """为 require_resolved() 设置当前解析上下文；返回传入的 resolver。"""
    _CONTEXT.resolver = resolver
    return resolver
