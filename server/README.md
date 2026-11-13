# 后端代码入口

目前尚无真实server.main。C实现FastAPI服务，B实现可被C导入的Agent函数。
已有tools/mock_api是独立接口联调工具，不要直接改名冒充真后端。
C/D约定真入口：python -m uvicorn server.main:app --host 127.0.0.1 --port 8765。
B不另开FastAPI服务，各岗位按INTEGRATION协作。
