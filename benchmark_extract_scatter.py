"""性能基准测试：extract_by_169_order 和 scatter_by_169_order"""

import time
import numpy as np
from bayes_poker.strategy.range.models import extract_by_169_order, scatter_by_169_order, PreflopRange

def benchmark_extract_scatter(iterations=10000):
    """测试 extract 和 scatter 的性能"""

    # 创建测试数据
    matrix = np.random.rand(13, 13).astype(np.float32)
    vector_169 = np.random.rand(169).astype(np.float32)

    # 测试 extract_by_169_order
    start = time.perf_counter()
    for _ in range(iterations):
        result = extract_by_169_order(matrix)
    extract_time = time.perf_counter() - start

    # 测试 scatter_by_169_order
    start = time.perf_counter()
    for _ in range(iterations):
        result = scatter_by_169_order(vector_169)
    scatter_time = time.perf_counter() - start

    # 测试完整的往返转换
    start = time.perf_counter()
    for _ in range(iterations):
        vec = extract_by_169_order(matrix)
        mat = scatter_by_169_order(vec)
    roundtrip_time = time.perf_counter() - start

    print(f"=== 性能基准测试 ({iterations} 次迭代) ===")
    print(f"extract_by_169_order: {extract_time*1000:.2f}ms ({extract_time/iterations*1e6:.2f}μs/次)")
    print(f"scatter_by_169_order: {scatter_time*1000:.2f}ms ({scatter_time/iterations*1e6:.2f}μs/次)")
    print(f"往返转换: {roundtrip_time*1000:.2f}ms ({roundtrip_time/iterations*1e6:.2f}μs/次)")
    print()

def benchmark_core_operations(iterations=10000):
    """对比核心操作的性能"""

    range1 = PreflopRange.from_list([0.5] * 169, [1.0] * 169)
    range2 = PreflopRange.from_list([0.3] * 169, [0.5] * 169)

    # 测试矩阵乘法（posterior 更新）
    start = time.perf_counter()
    for _ in range(iterations):
        result = range1.strategy * range2.strategy
    multiply_time = time.perf_counter() - start

    # 测试 total_frequency（加权求和）
    start = time.perf_counter()
    for _ in range(iterations):
        freq = range1.total_frequency()
    total_freq_time = time.perf_counter() - start

    # 测试 normalize（原地修改）
    start = time.perf_counter()
    for _ in range(iterations):
        r = PreflopRange.from_list([0.5] * 169, [1.0] * 169)
        r.normalize()
    normalize_time = time.perf_counter() - start

    print(f"=== 核心操作性能 ({iterations} 次迭代) ===")
    print(f"矩阵乘法: {multiply_time*1000:.2f}ms ({multiply_time/iterations*1e6:.2f}μs/次)")
    print(f"total_frequency: {total_freq_time*1000:.2f}ms ({total_freq_time/iterations*1e6:.2f}μs/次)")
    print(f"normalize: {normalize_time*1000:.2f}ms ({normalize_time/iterations*1e6:.2f}μs/次)")
    print()

if __name__ == "__main__":
    benchmark_extract_scatter()
    benchmark_core_operations()

    print("=== 结论 ===")
    print("如果 extract/scatter 时间 << 核心操作时间，则不是瓶颈")
