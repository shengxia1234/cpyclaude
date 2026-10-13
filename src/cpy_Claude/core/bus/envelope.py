from pydantic import BaseModel,Field
from typing import Any,Literal


class JsonRpcRequest(BaseModel):
    jsonrpc : Literal["2.0"] = "2.0"
    id : str | None = None
    method : str
    params : dict[str,Any] = Field(default_factory=dict)

class JsonRpcSuccess(BaseModel):
    jsonrpc : Literal["2.0"] = "2.0"
    id : str | None = None
    result : Any

class JsonRpcErrorObj(BaseModel):
    code : int
    message : str
    data : Any = None

class JsonRpcError(BaseModel):
    jsonrpc : Literal["2.0"] = "2.0"
    id : str | None = None
    error : JsonRpcErrorObj

PARSE_ERROR = -32700      # 解析错误
INVALID_REQUEST = -32600  # 请求格式错误
METHOD_NOT_FOUND = -32601 # 方法不存在
INVALID_PARAMS = -32602   # 参数错误
INTERNAL_ERROR = -32603   # 服务器内部错误

#返回JsonRpcError实例
def make_error(id : str | None,code : int,msg : str,data : Any = None) -> JsonRpcError:
    return JsonRpcError(id=id,error=JsonRpcErrorObj(code=code,message=msg,data=data))