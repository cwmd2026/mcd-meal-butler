# MCP 集成说明

本项目是一个 **WorkBuddy Skill**（非服务器），由 Agent 直接编排麦当劳中国官方远程 MCP 工具，
完成「多人点单 → 最省精算 → AA 分账 → 开饭海报 → 可选下单」全链路。

## 一、使用的 MCP Server

| 项目 | 值 |
|---|---|
| MCP Server | 麦当劳中国官方远程 MCP Server |
| 接入地址 | `https://mcp.mcd.cn` |
| 传输协议 | Streamable HTTP |
| 认证方式 | 请求头 `Authorization: Bearer ${MCD_MCP_TOKEN}` |
| 限流 | 每 Token 600 次/分钟（超限 429） |
| 官方文档 | <https://github.com/M-China/mcd-mcp-server> |
| 脱敏配置 | 见 [`mcp-config.example.json`](mcp-config.example.json) |

> Token 仅通过环境变量注入，仓库内不含任何真实凭据。

## 二、使用的 MCP Tools

> 以下参数规则经 2026-10-09 真实接口实测验证（35 个工具在线，schema 以服务端实时返回为准）。

| # | Tool | 在本项目中的用途 | 关键参数（实测） |
|---|---|---|---|
| 1 | `query-nearby-stores` | 到店/得来速选门店 | `beType`(1/5) + `searchType`(1/2) 必传；位置搜索传 `city`+`keyword`；返回 `storeCode`(beType=5 另有 `beCode`) |
| 2 | `query-meals` | 拉菜单、建「名称→编码」索引 | `storeCode`+`orderType`(1/2)+`beType`(1/2/5/6) 必传；到店自提不传 `beCode`，得来速/外送/团餐必传；返回 `data.categories[].meals[]` + `data.meals{code→详情}` |
| 3 | `query-meal-detail` | 查套餐组成与可换项（"可乐换无糖"） | `productCode` |
| 4 | `calculate-price` | **核心精算**：逐方案算实付 | `items:[{productCode, quantity, couponId?, modification?}]`；**返回价格单位为分，展示 ÷100** |
| 5 | `query-my-coupons` | 读用户卡包挑最优券 | `page`/`pageSize`；真实返回为 markdown 文本 |
| 6 | `auto-bind-coupons` | 精算前一键领券 | — |
| 7 | `query-my-account` | 读积分（优先消耗将过期积分） | 返回 `availablePoint`/`currentMothExpirePoint` |
| 8 | `mall-points-products` | 查积分可兑换商品，构造积分方案 | — |
| 9 | `mall-product-detail` | 兑换商品价值评估 | — |
| 10 | `delivery-query-stores` | 外送/团餐场景选可配送门店 | — |
| 11 | `campaign-calendar` | 判断有无可叠加优惠 | — |
| 12 | `create-order` | 用户确认后生成订单与支付链接 | — |

**实测校验样例**（上海黄浦华旭国际大厦餐厅 storeCode=1450713，到店自提）：
巨无霸三件套 ¥36.5 + 中薯条 ¥13.5 + 麦乐鸡经典中套餐 ¥25.0 → `calculate-price` 返回 7500 分 = **¥75.00**，与菜单单价加总分毫不差；AA 分账 36.5+25.0+13.5=75.0 守恒。

**解析注意**：工具返回的 text 是「字段说明 markdown + 正文 JSON」拼接，需提取 `{"success":...}` JSON 段。菜单**分时段供应**（如凌晨无麦辣/麦旋风），匹配不到必须如实告知。

## 三、调用流程

```
多人点单文本
   │  Agent（本身即 LLM）解析成结构化订单
   ▼
query-nearby-stores / delivery-query-stores（选门店，拿 storeCode/beCode）
   ▼
query-meals（categories + meals 映射，匹配商品码）
   ▼
基线：calculate-price（无优惠实付）          ← 价格单位：分
   ▼
方案A：calculate-price + 最优券（query-my-coupons，items[].couponId 挂券）
方案B：calculate-price + 积分兑换（query-my-account + mall-points-products）
方案C：calculate-price + 积分兑换部分 + 券点其余
   ▼
全部 ÷100 转元 → 取实付最低 → AA 分账（按各人餐品占比，金额守恒）
   ▼
scripts/poster.py 生成开饭海报（可选 create-order 下单）
```

核心精算：构造 A/B/C 三套方案并逐套 `calculate-price`，取实付最低。
**口径**：`节省 = 无优惠实付基线 − 本方案实付`（含配送费影响）；积分兑换价值标注"估算"。

## 四、业务价值

| 痛点 | 本项目如何解决 | 依赖的 MCP 能力 |
|---|---|---|
| 群聊点单信息散乱、人工统计易错 | Agent 自动解析成结构化订单，逐人逐项归类 | Agent + 订单模型 |
| 券/积分/商城组合太复杂，算不清最省 | 多方案自动精算，一键给最优解 | `calculate-price`、`query-my-coupons`、`mall-points-products` |
| 积分、券放过期 | 精算前领券，积分优先消耗 | `auto-bind-coupons`、`query-my-account` |
| 凑满减、算配送费麻烦 | 逐方案含配送费实付对比 | `calculate-price` |
| 点完还要人工 AA | 按餐品占比自动分账 | 订单模型 + 精算结果 |
| 想晒、想攒气氛 | 生成可转发的开饭海报与"麦当劳之王"战报 | `scripts/poster.py` |

## 五、安全与合规

- Token 走环境变量，`mcp-config.example.json` 仅含占位符。
- 写操作（`create-order`、积分兑换）**只在用户明确确认后触发**。
- 展示个人信息时脱敏，不采集与点餐无关数据。
- 价格/库存/优惠以 MCP 实时返回为准，不臆造数据。
