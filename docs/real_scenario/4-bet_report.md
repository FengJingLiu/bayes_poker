# 4-Bet 场景测试报告

总耗时: 169352.2ms

## 数据不足 (<50手)

### 紧被动 (低VPIP/低PFR)

| 位置组合 | 玩家 | 手数 | VPIP | PFR | 先验分布 | 后验分布 | 耗时(ms) |
|---------|------|------|------|-----|---------|---------|----------|
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | xMichax | 4 | 0.0% | 0.0% | F:98% R26:1% RAI:0% | F:99% R26:1% RAI:0% | 27.9 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | xMichax | 4 | 0.0% | 0.0% | F:98% R29:1% RAI:0% | F:99% R29:1% RAI:0% | 27.6 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | xMichax | 4 | 0.0% | 0.0% | F:98% R29:1% RAI:0% | F:99% R29:1% RAI:0% | 28.2 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | xMichax | 4 | 0.0% | 0.0% | F:98% R28:1% RAI:1% | F:99% R28:1% RAI:0% | 28.2 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | xMichax | 4 | 0.0% | 0.0% | F:98% R28:1% RAI:1% | F:99% R28:1% RAI:0% | 28.4 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | xMichax | 4 | 0.0% | 0.0% | F:98% R35:1% RAI:1% | F:99% R35:0% RAI:1% | 28.1 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | xMichax | 4 | 0.0% | 0.0% | F:98% R29:1% RAI:1% | F:99% R29:1% RAI:0% | 28.1 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | xMichax | 4 | 0.0% | 0.0% | F:98% R28:1% RAI:1% | F:99% R28:1% RAI:1% | 29.0 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | xMichax | 4 | 0.0% | 0.0% | F:98% R35:0% RAI:1% | F:99% R35:0% RAI:1% | 28.5 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | xMichax | 4 | 0.0% | 0.0% | F:98% R36:0% RAI:2% | F:99% R36:0% RAI:1% | 29.2 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | xMichax | 4 | 0.0% | 0.0% | F:47% C:19% R41:0% RAI:34% | F:58% C:23% R41:0% RAI:19% | 29.0 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | xMichax | 4 | 0.0% | 0.0% | F:98% R28:1% RAI:2% | F:99% R28:0% RAI:1% | 28.5 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | xMichax | 4 | 0.0% | 0.0% | F:98% R35:0% RAI:2% | F:99% R35:0% RAI:1% | 28.9 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | xMichax | 4 | 0.0% | 0.0% | F:98% R35:0% RAI:2% | F:99% R35:0% RAI:1% | 29.0 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | xMichax | 4 | 0.0% | 0.0% | F:98% R35:0% RAI:2% | F:99% R35:0% RAI:1% | 29.0 |

### 紧激进 (低VPIP/高PFR)

| 位置组合 | 玩家 | 手数 | VPIP | PFR | 先验分布 | 后验分布 | 耗时(ms) |
|---------|------|------|------|-----|---------|---------|----------|
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | elvq | 12 | 16.7% | 16.7% | F:98% R26:1% RAI:0% | F:95% R26:4% RAI:1% | 627.9 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | elvq | 12 | 16.7% | 16.7% | F:98% R29:1% RAI:0% | F:95% R29:3% RAI:1% | 629.2 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | elvq | 12 | 16.7% | 16.7% | F:98% R29:1% RAI:0% | F:95% R29:3% RAI:1% | 626.7 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | elvq | 12 | 16.7% | 16.7% | F:98% R28:1% RAI:1% | F:95% R28:3% RAI:2% | 629.8 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | elvq | 12 | 16.7% | 16.7% | F:98% R28:1% RAI:1% | F:95% R28:3% RAI:2% | 630.4 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | elvq | 12 | 16.7% | 16.7% | F:98% R35:1% RAI:1% | F:94% R35:2% RAI:4% | 630.5 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | elvq | 12 | 16.7% | 16.7% | F:98% R29:1% RAI:1% | F:96% R29:3% RAI:1% | 627.7 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | elvq | 12 | 16.7% | 16.7% | F:98% R28:1% RAI:1% | F:95% R28:3% RAI:2% | 629.8 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | elvq | 12 | 16.7% | 16.7% | F:98% R35:0% RAI:1% | F:94% R35:1% RAI:4% | 630.6 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | elvq | 12 | 16.7% | 16.7% | F:98% R36:0% RAI:2% | F:95% R36:1% RAI:4% | 631.6 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | elvq | 12 | 16.7% | 16.7% | F:47% C:19% R41:0% RAI:34% | F:22% C:9% R41:0% RAI:70% | 624.6 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | elvq | 12 | 16.7% | 16.7% | F:98% R28:1% RAI:2% | F:95% R28:1% RAI:3% | 631.1 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | elvq | 12 | 16.7% | 16.7% | F:98% R35:0% RAI:2% | F:95% R35:0% RAI:5% | 635.4 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | elvq | 12 | 16.7% | 16.7% | F:98% R35:0% RAI:2% | F:96% R35:0% RAI:4% | 630.4 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | elvq | 12 | 16.7% | 16.7% | F:98% R35:0% RAI:2% | F:97% R35:0% RAI:3% | 1079.4 |

### 松被动 (高VPIP/低PFR)

| 位置组合 | 玩家 | 手数 | VPIP | PFR | 先验分布 | 后验分布 | 耗时(ms) |
|---------|------|------|------|-----|---------|---------|----------|
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | afclockey49 | 6 | 83.3% | 0.0% | F:98% R26:1% RAI:0% | F:99% R26:1% RAI:0% | 27.9 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:98% R29:1% RAI:0% | F:99% R29:1% RAI:0% | 27.8 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:98% R29:1% RAI:0% | F:99% R29:1% RAI:0% | 27.9 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:98% R28:1% RAI:1% | F:99% R28:1% RAI:0% | 28.2 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:98% R28:1% RAI:1% | F:99% R28:1% RAI:0% | 28.3 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:98% R35:1% RAI:1% | F:99% R35:0% RAI:1% | 28.3 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:98% R29:1% RAI:1% | F:99% R29:1% RAI:0% | 466.3 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:98% R28:1% RAI:1% | F:99% R28:1% RAI:1% | 28.5 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:98% R35:0% RAI:1% | F:99% R35:0% RAI:1% | 28.6 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:98% R36:0% RAI:2% | F:99% R36:0% RAI:1% | 29.1 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:47% C:19% R41:0% RAI:34% | F:58% C:23% R41:0% RAI:19% | 28.3 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:98% R28:1% RAI:2% | F:99% R28:0% RAI:1% | 28.8 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:98% R35:0% RAI:2% | F:99% R35:0% RAI:1% | 28.9 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:98% R35:0% RAI:2% | F:99% R35:0% RAI:1% | 28.9 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:98% R35:0% RAI:2% | F:99% R35:0% RAI:1% | 29.2 |

### 松激进 (高VPIP/高PFR)

| 位置组合 | 玩家 | 手数 | VPIP | PFR | 先验分布 | 后验分布 | 耗时(ms) |
|---------|------|------|------|-----|---------|---------|----------|
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | Badforyou | 10 | 30.0% | 22.2% | F:98% R26:1% RAI:0% | F:93% R26:5% RAI:2% | 621.7 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | Badforyou | 10 | 30.0% | 22.2% | F:98% R29:1% RAI:0% | F:93% R29:5% RAI:2% | 619.6 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | Badforyou | 10 | 30.0% | 22.2% | F:98% R29:1% RAI:0% | F:93% R29:5% RAI:2% | 623.0 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Badforyou | 10 | 30.0% | 22.2% | F:98% R28:1% RAI:1% | F:93% R28:5% RAI:2% | 619.3 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Badforyou | 10 | 30.0% | 22.2% | F:98% R28:1% RAI:1% | F:93% R28:5% RAI:2% | 618.3 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Badforyou | 10 | 30.0% | 22.2% | F:98% R35:1% RAI:1% | F:92% R35:3% RAI:6% | 620.6 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Badforyou | 10 | 30.0% | 22.2% | F:98% R29:1% RAI:1% | F:93% R29:5% RAI:2% | 620.8 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Badforyou | 10 | 30.0% | 22.2% | F:98% R28:1% RAI:1% | F:93% R28:4% RAI:3% | 619.7 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Badforyou | 10 | 30.0% | 22.2% | F:98% R35:0% RAI:1% | F:92% R35:2% RAI:6% | 628.4 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Badforyou | 10 | 30.0% | 22.2% | F:98% R36:0% RAI:2% | F:92% R36:1% RAI:6% | 621.4 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Badforyou | 10 | 30.0% | 22.2% | F:47% C:19% R41:0% RAI:34% | F:47% C:19% R41:0% RAI:34% | 618.6 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Badforyou | 10 | 30.0% | 22.2% | F:98% R28:1% RAI:2% | F:93% R28:2% RAI:5% | 624.3 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Badforyou | 10 | 30.0% | 22.2% | F:98% R35:0% RAI:2% | F:92% R35:1% RAI:7% | 622.1 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Badforyou | 10 | 30.0% | 22.2% | F:98% R35:0% RAI:2% | F:93% R35:1% RAI:6% | 621.6 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Badforyou | 10 | 30.0% | 22.2% | F:98% R35:0% RAI:2% | F:95% R35:0% RAI:5% | 627.2 |

## 数据中等 (50-300手)

### 紧被动 (低VPIP/低PFR)

| 位置组合 | 玩家 | 手数 | VPIP | PFR | 先验分布 | 后验分布 | 耗时(ms) |
|---------|------|------|------|-----|---------|---------|----------|
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | Turbem | 116 | 22.4% | 15.0% | F:98% R26:1% RAI:0% | F:96% R26:3% RAI:1% | 1068.5 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | Turbem | 116 | 22.4% | 15.0% | F:98% R29:1% RAI:0% | F:96% R29:3% RAI:1% | 1060.4 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | Turbem | 116 | 22.4% | 15.0% | F:98% R29:1% RAI:0% | F:96% R29:3% RAI:1% | 1057.6 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Turbem | 116 | 22.4% | 15.0% | F:98% R28:1% RAI:1% | F:96% R28:3% RAI:1% | 1052.1 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Turbem | 116 | 22.4% | 15.0% | F:98% R28:1% RAI:1% | F:96% R28:3% RAI:1% | 1539.0 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Turbem | 116 | 22.4% | 15.0% | F:98% R35:1% RAI:1% | F:95% R35:2% RAI:3% | 1055.2 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Turbem | 116 | 22.4% | 15.0% | F:98% R29:1% RAI:1% | F:96% R29:3% RAI:1% | 1076.2 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Turbem | 116 | 22.4% | 15.0% | F:98% R28:1% RAI:1% | F:95% R28:3% RAI:2% | 1058.7 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Turbem | 116 | 22.4% | 15.0% | F:98% R35:0% RAI:1% | F:95% R35:1% RAI:4% | 1061.0 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Turbem | 116 | 22.4% | 15.0% | F:98% R36:0% RAI:2% | F:95% R36:1% RAI:4% | 1056.8 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Turbem | 116 | 22.4% | 15.0% | F:47% C:19% R41:0% RAI:34% | F:22% C:9% R41:0% RAI:69% | 1064.0 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Turbem | 116 | 22.4% | 15.0% | F:98% R28:1% RAI:2% | F:95% R28:1% RAI:3% | 1068.8 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Turbem | 116 | 22.4% | 15.0% | F:98% R35:0% RAI:2% | F:95% R35:0% RAI:5% | 1066.3 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Turbem | 116 | 22.4% | 15.0% | F:98% R35:0% RAI:2% | F:96% R35:0% RAI:4% | 1070.1 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Turbem | 116 | 22.4% | 15.0% | F:98% R35:0% RAI:2% | F:97% R35:0% RAI:2% | 1082.1 |

### 紧激进 (低VPIP/高PFR)

| 位置组合 | 玩家 | 手数 | VPIP | PFR | 先验分布 | 后验分布 | 耗时(ms) |
|---------|------|------|------|-----|---------|---------|----------|
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | iprayforgod | 129 | 23.3% | 21.4% | F:98% R26:1% RAI:0% | F:93% R26:5% RAI:2% | 1320.4 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:98% R29:1% RAI:0% | F:93% R29:5% RAI:2% | 1327.6 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:98% R29:1% RAI:0% | F:93% R29:5% RAI:2% | 1326.0 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:98% R28:1% RAI:1% | F:93% R28:4% RAI:2% | 1329.9 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:98% R28:1% RAI:1% | F:93% R28:4% RAI:2% | 1339.9 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:98% R35:1% RAI:1% | F:92% R35:2% RAI:5% | 1328.3 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:98% R29:1% RAI:1% | F:94% R29:4% RAI:2% | 1327.5 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:98% R28:1% RAI:1% | F:94% R28:3% RAI:3% | 1346.0 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:98% R35:0% RAI:1% | F:93% R35:2% RAI:5% | 1328.0 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:98% R36:0% RAI:2% | F:93% R36:1% RAI:6% | 1339.3 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:47% C:19% R41:0% RAI:34% | F:4% C:1% R41:0% RAI:95% | 1335.0 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:98% R28:1% RAI:2% | F:94% R28:2% RAI:5% | 1344.4 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:98% R35:0% RAI:2% | F:93% R35:1% RAI:6% | 1825.2 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:98% R35:0% RAI:2% | F:94% R35:1% RAI:6% | 1336.6 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:98% R35:0% RAI:2% | F:95% R35:0% RAI:5% | 1342.1 |

### 松被动 (高VPIP/低PFR)

| 位置组合 | 玩家 | 手数 | VPIP | PFR | 先验分布 | 后验分布 | 耗时(ms) |
|---------|------|------|------|-----|---------|---------|----------|
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | aafhs | 100 | 28.0% | 12.5% | F:98% R26:1% RAI:0% | F:97% R26:2% RAI:1% | 1118.4 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | aafhs | 100 | 28.0% | 12.5% | F:98% R29:1% RAI:0% | F:97% R29:2% RAI:1% | 1552.7 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | aafhs | 100 | 28.0% | 12.5% | F:98% R29:1% RAI:0% | F:97% R29:2% RAI:1% | 1110.4 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | aafhs | 100 | 28.0% | 12.5% | F:98% R28:1% RAI:1% | F:97% R28:2% RAI:1% | 1105.0 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | aafhs | 100 | 28.0% | 12.5% | F:98% R28:1% RAI:1% | F:97% R28:2% RAI:1% | 1118.0 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | aafhs | 100 | 28.0% | 12.5% | F:98% R35:1% RAI:1% | F:97% R35:1% RAI:2% | 1116.1 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | aafhs | 100 | 28.0% | 12.5% | F:98% R29:1% RAI:1% | F:97% R29:2% RAI:1% | 1113.5 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | aafhs | 100 | 28.0% | 12.5% | F:98% R28:1% RAI:1% | F:97% R28:2% RAI:1% | 1110.1 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | aafhs | 100 | 28.0% | 12.5% | F:98% R35:0% RAI:1% | F:97% R35:1% RAI:2% | 1116.4 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | aafhs | 100 | 28.0% | 12.5% | F:98% R36:0% RAI:2% | F:97% R36:0% RAI:3% | 1123.5 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | aafhs | 100 | 28.0% | 12.5% | F:47% C:19% R41:0% RAI:34% | F:40% C:16% R41:0% RAI:45% | 1114.5 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | aafhs | 100 | 28.0% | 12.5% | F:98% R28:1% RAI:2% | F:97% R28:1% RAI:2% | 1126.0 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | aafhs | 100 | 28.0% | 12.5% | F:98% R35:0% RAI:2% | F:97% R35:0% RAI:3% | 1125.6 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | aafhs | 100 | 28.0% | 12.5% | F:98% R35:0% RAI:2% | F:97% R35:0% RAI:3% | 1123.5 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | aafhs | 100 | 28.0% | 12.5% | F:98% R35:0% RAI:2% | F:98% R35:0% RAI:2% | 1120.2 |

### 松激进 (高VPIP/高PFR)

| 位置组合 | 玩家 | 手数 | VPIP | PFR | 先验分布 | 后验分布 | 耗时(ms) |
|---------|------|------|------|-----|---------|---------|----------|
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | Oatta | 108 | 38.9% | 27.0% | F:98% R26:1% RAI:0% | F:92% R26:6% RAI:2% | 1246.1 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | Oatta | 108 | 38.9% | 27.0% | F:98% R29:1% RAI:0% | F:92% R29:6% RAI:2% | 1260.9 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | Oatta | 108 | 38.9% | 27.0% | F:98% R29:1% RAI:0% | F:92% R29:6% RAI:2% | 1260.3 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Oatta | 108 | 38.9% | 27.0% | F:98% R28:1% RAI:1% | F:92% R28:6% RAI:3% | 1246.7 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Oatta | 108 | 38.9% | 27.0% | F:98% R28:1% RAI:1% | F:92% R28:6% RAI:3% | 1250.2 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Oatta | 108 | 38.9% | 27.0% | F:98% R35:1% RAI:1% | F:92% R35:3% RAI:6% | 1246.5 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Oatta | 108 | 38.9% | 27.0% | F:98% R29:1% RAI:1% | F:92% R29:6% RAI:3% | 1243.4 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Oatta | 108 | 38.9% | 27.0% | F:98% R28:1% RAI:1% | F:91% R28:5% RAI:4% | 1248.5 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Oatta | 108 | 38.9% | 27.0% | F:98% R35:0% RAI:1% | F:92% R35:2% RAI:6% | 1259.5 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Oatta | 108 | 38.9% | 27.0% | F:98% R36:0% RAI:2% | F:91% R36:1% RAI:8% | 1747.8 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Oatta | 108 | 38.9% | 27.0% | F:47% C:19% R41:0% RAI:34% | F:47% C:19% R41:0% RAI:34% | 1253.5 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Oatta | 108 | 38.9% | 27.0% | F:98% R28:1% RAI:2% | F:91% R28:2% RAI:7% | 1260.8 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Oatta | 108 | 38.9% | 27.0% | F:98% R35:0% RAI:2% | F:90% R35:1% RAI:9% | 1269.0 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Oatta | 108 | 38.9% | 27.0% | F:98% R35:0% RAI:2% | F:92% R35:1% RAI:8% | 1262.0 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Oatta | 108 | 38.9% | 27.0% | F:98% R35:0% RAI:2% | F:94% R35:1% RAI:6% | 1257.9 |

## 数据充足 (>300手)

### 紧被动 (低VPIP/低PFR)

| 位置组合 | 玩家 | 手数 | VPIP | PFR | 先验分布 | 后验分布 | 耗时(ms) |
|---------|------|------|------|-----|---------|---------|----------|
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | oleh2222 | 802 | 12.0% | 8.2% | F:98% R26:1% RAI:0% | F:99% R26:1% RAI:0% | 1304.5 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:98% R29:1% RAI:0% | F:99% R29:1% RAI:0% | 1286.0 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:98% R29:1% RAI:0% | F:99% R29:1% RAI:0% | 1722.7 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:98% R28:1% RAI:1% | F:99% R28:1% RAI:0% | 1279.0 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:98% R28:1% RAI:1% | F:99% R28:1% RAI:0% | 1272.0 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:98% R35:1% RAI:1% | F:99% R35:0% RAI:1% | 1269.5 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:98% R29:1% RAI:1% | F:99% R29:1% RAI:0% | 1286.1 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:98% R28:1% RAI:1% | F:99% R28:1% RAI:0% | 1279.4 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:98% R35:0% RAI:1% | F:99% R35:0% RAI:1% | 1284.1 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:98% R36:0% RAI:2% | F:99% R36:0% RAI:1% | 1289.4 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:47% C:19% R41:0% RAI:34% | F:57% C:23% R41:0% RAI:20% | 1736.4 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:98% R28:1% RAI:2% | F:99% R28:0% RAI:1% | 1300.0 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:98% R35:0% RAI:2% | F:99% R35:0% RAI:1% | 1301.1 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:98% R35:0% RAI:2% | F:99% R35:0% RAI:1% | 1295.5 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:98% R35:0% RAI:2% | F:99% R35:0% RAI:1% | 1309.5 |

### 紧激进 (低VPIP/高PFR)

| 位置组合 | 玩家 | 手数 | VPIP | PFR | 先验分布 | 后验分布 | 耗时(ms) |
|---------|------|------|------|-----|---------|---------|----------|
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | Noris22 | 1124 | 24.6% | 16.1% | F:98% R26:1% RAI:0% | F:96% R26:3% RAI:1% | 1185.5 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:98% R29:1% RAI:0% | F:96% R29:3% RAI:1% | 1186.3 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:98% R29:1% RAI:0% | F:96% R29:3% RAI:1% | 1175.2 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:98% R28:1% RAI:1% | F:96% R28:2% RAI:1% | 1183.6 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:98% R28:1% RAI:1% | F:96% R28:2% RAI:1% | 1207.8 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:98% R35:1% RAI:1% | F:96% R35:1% RAI:3% | 1184.3 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:98% R29:1% RAI:1% | F:97% R29:2% RAI:1% | 1191.2 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:98% R28:1% RAI:1% | F:97% R28:2% RAI:1% | 1192.8 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:98% R35:0% RAI:1% | F:96% R35:1% RAI:3% | 1201.2 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:98% R36:0% RAI:2% | F:97% R36:0% RAI:3% | 1194.8 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:47% C:19% R41:0% RAI:34% | F:35% C:14% R41:0% RAI:52% | 1206.4 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:98% R28:1% RAI:2% | F:97% R28:1% RAI:3% | 1217.9 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:98% R35:0% RAI:2% | F:96% R35:0% RAI:3% | 1201.1 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:98% R35:0% RAI:2% | F:97% R35:0% RAI:3% | 1192.0 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:98% R35:0% RAI:2% | F:98% R35:0% RAI:2% | 1202.5 |

### 松被动 (高VPIP/低PFR)

| 位置组合 | 玩家 | 手数 | VPIP | PFR | 先验分布 | 后验分布 | 耗时(ms) |
|---------|------|------|------|-----|---------|---------|----------|
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | Dorororoo | 535 | 32.7% | 13.2% | F:98% R26:1% RAI:0% | F:96% R26:3% RAI:1% | 1050.6 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:98% R29:1% RAI:0% | F:96% R29:3% RAI:1% | 1053.0 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:98% R29:1% RAI:0% | F:96% R29:3% RAI:1% | 1040.7 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:98% R28:1% RAI:1% | F:97% R28:2% RAI:1% | 1045.3 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:98% R28:1% RAI:1% | F:97% R28:2% RAI:1% | 1050.2 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:98% R35:1% RAI:1% | F:96% R35:1% RAI:3% | 1048.1 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:98% R29:1% RAI:1% | F:97% R29:2% RAI:1% | 1045.4 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:98% R28:1% RAI:1% | F:97% R28:2% RAI:1% | 1521.0 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:98% R35:0% RAI:1% | F:96% R35:1% RAI:3% | 1060.2 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:98% R36:0% RAI:2% | F:97% R36:0% RAI:3% | 1055.5 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:47% C:19% R41:0% RAI:34% | F:43% C:17% R41:0% RAI:39% | 1056.8 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:98% R28:1% RAI:2% | F:97% R28:1% RAI:2% | 1061.4 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:98% R35:0% RAI:2% | F:97% R35:0% RAI:3% | 1066.1 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:98% R35:0% RAI:2% | F:98% R35:0% RAI:2% | 1054.4 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:98% R35:0% RAI:2% | F:98% R35:0% RAI:2% | 1058.0 |

### 松激进 (高VPIP/高PFR)

| 位置组合 | 玩家 | 手数 | VPIP | PFR | 先验分布 | 后验分布 | 耗时(ms) |
|---------|------|------|------|-----|---------|---------|----------|
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | Deteuler | 638 | 27.0% | 21.4% | F:98% R26:1% RAI:0% | F:94% R26:4% RAI:2% | 1390.3 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | Deteuler | 638 | 27.0% | 21.4% | F:98% R29:1% RAI:0% | F:94% R29:4% RAI:2% | 1396.5 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | Deteuler | 638 | 27.0% | 21.4% | F:98% R29:1% RAI:0% | F:94% R29:4% RAI:2% | 1389.2 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Deteuler | 638 | 27.0% | 21.4% | F:98% R28:1% RAI:1% | F:95% R28:4% RAI:2% | 1395.2 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Deteuler | 638 | 27.0% | 21.4% | F:98% R28:1% RAI:1% | F:95% R28:4% RAI:2% | 1407.8 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Deteuler | 638 | 27.0% | 21.4% | F:98% R35:1% RAI:1% | F:94% R35:2% RAI:4% | 1395.4 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Deteuler | 638 | 27.0% | 21.4% | F:98% R29:1% RAI:1% | F:95% R29:4% RAI:2% | 1392.2 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Deteuler | 638 | 27.0% | 21.4% | F:98% R28:1% RAI:1% | F:94% R28:3% RAI:2% | 1390.5 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Deteuler | 638 | 27.0% | 21.4% | F:98% R35:0% RAI:1% | F:94% R35:2% RAI:5% | 1404.4 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Deteuler | 638 | 27.0% | 21.4% | F:98% R36:0% RAI:2% | F:94% R36:1% RAI:5% | 1403.2 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Deteuler | 638 | 27.0% | 21.4% | F:47% C:19% R41:0% RAI:34% | F:12% C:5% R41:0% RAI:83% | 1396.4 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Deteuler | 638 | 27.0% | 21.4% | F:98% R28:1% RAI:2% | F:94% R28:1% RAI:4% | 1406.2 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Deteuler | 638 | 27.0% | 21.4% | F:98% R35:0% RAI:2% | F:94% R35:1% RAI:5% | 1408.3 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Deteuler | 638 | 27.0% | 21.4% | F:98% R35:0% RAI:2% | F:95% R35:0% RAI:4% | 1402.1 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Deteuler | 638 | 27.0% | 21.4% | F:98% R35:0% RAI:2% | F:96% R35:0% RAI:4% | 1404.5 |

