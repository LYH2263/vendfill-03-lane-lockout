# VendFill 售货机补货

按货道容量、库存与在途量计算缺口，生成不超缺口、非负的补货单。

技术栈：Python 3.12 / FastAPI / SQLAlchemy / PostgreSQL / Vue 3 / TypeScript / Vite

## 启动

```bash
docker compose up --build
```

| 服务 | 地址 |
| --- | --- |
| 前端 | http://localhost:4800 |
| API | http://localhost:9800 |
| API 文档 | http://localhost:9800/docs |
| Postgres | localhost:5449 |

健康检查：`GET http://localhost:9800/api/health`

## 使用说明

1. 在「点位」「货道」查看售货机布局与库存。
2. 在「销量」了解近期出货。
3. 打开「补货单」按缺口生成建议补货量。
4. 在「满仓」「汇总」查看已满货道与补货合计。
5. 在「货道格子」可对货道标记/解除「检修封锁」：封锁道补量恒为 0，原因只记「货道封锁」，且与满仓互斥（不进满仓页）。保存封锁时，货道旗标与该点位当前有效补货单在同一事务内更新，任一失败两者一起回滚；更早的补货单文本保持生成当时样子。

## 开发与测试

```bash
docker compose exec api pytest -q
```
