"""
Algorithms API router.

Returns available algorithms and their parameter schemas.
"""

from fastapi import APIRouter

from smart_threshold.algorithms import AlgorithmRegistry
from backend.app.schemas import AlgorithmInfo, AlgorithmListResponse

router = APIRouter()


@router.get(
    "",
    response_model=AlgorithmListResponse,
    summary="获取所有算法列表",
    description="返回所有可用的预测算法及其参数 Schema。参数 Schema 为 JSON Schema draft-07 格式，可用于前端动态表单渲染。",
)
async def list_algorithms():
    algorithms = [
        AlgorithmInfo(
            id=info["id"],
            name=info["name"],
            description=info["description"],
            param_schema=info["param_schema"],
        )
        for info in AlgorithmRegistry.get_all_info()
    ]

    return AlgorithmListResponse(algorithms=algorithms)


@router.get(
    "/{algorithm_id}",
    response_model=AlgorithmInfo,
    summary="获取算法详情",
    description="获取指定算法的详细信息，包括名称、描述和参数 Schema。",
)
async def get_algorithm(algorithm_id: str):
    algo_class = AlgorithmRegistry.get(algorithm_id)
    if algo_class is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Algorithm not found: {algorithm_id}")

    info = algo_class.get_algorithm_info()
    return AlgorithmInfo(
        id=info["id"],
        name=info["name"],
        description=info["description"],
        param_schema=info["param_schema"],
    )