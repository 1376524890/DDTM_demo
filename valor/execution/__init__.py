"""交付执行层（规范 §36/§27）。

- access_handle:   数据访问句柄（§27）
- download_traceable: DOWNLOAD_TRACEABLE（可追溯副本，不声称能阻止离线复制）
- api_gateway:      API_GATEWAY（所有查询经 PEP）
- compute_only:     COMPUTE_ONLY（数据留在控制域，只返回允许输出）
- fingerprint:      接收方指纹（可追溯）
"""

from .download_traceable import DownloadTraceableDelivery
from .compute_only import ComputeOnlyDelivery

__all__ = ["DownloadTraceableDelivery", "ComputeOnlyDelivery"]
