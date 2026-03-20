# Facing_3-Bet 场景测试报告

总耗时: 56877.8ms

## 数据不足 (<50手)

### 紧被动 (低VPIP/低PFR)

| 位置组合 | 玩家 | 手数 | VPIP | PFR | 先验分布 | 后验分布 | 耗时(ms) |
|---------|------|------|------|-----|---------|---------|----------|
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>) | xMichax | 4 | 0.0% | 0.0% | F:62% C:16% R20:23% | F:65% C:16% R20:19% | 10.2 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>) | xMichax | 4 | 0.0% | 0.0% | F:61% C:15% R20:25% | F:63% C:15% R20:22% | 10.5 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>) | xMichax | 4 | 0.0% | 0.0% | F:60% C:13% R20:27% | F:59% C:13% R20:28% | 10.7 |
| (<Position.UTG: 'UTG'>, <Position.SB: 'SB'>) | xMichax | 4 | 0.0% | 0.0% | F:64% C:19% R21:17% | F:63% C:19% R21:19% | 10.8 |
| (<Position.UTG: 'UTG'>, <Position.BB: 'BB'>) | xMichax | 4 | 0.0% | 0.0% | F:63% C:23% R22:14% | F:61% C:22% R22:17% | 11.3 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>) | xMichax | 4 | 0.0% | 0.0% | F:63% C:14% R20:24% | F:66% C:15% R20:19% | 10.4 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>) | xMichax | 4 | 0.0% | 0.0% | F:61% C:13% R20:26% | F:63% C:14% R20:24% | 10.8 |
| (<Position.MP: 'MP'>, <Position.SB: 'SB'>) | xMichax | 4 | 0.0% | 0.0% | F:71% C:9% R23:19% | F:71% C:9% R23:20% | 10.9 |
| (<Position.MP: 'MP'>, <Position.BB: 'BB'>) | xMichax | 4 | 0.0% | 0.0% | F:64% C:20% R24:16% | F:63% C:20% R24:17% | 11.4 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | xMichax | 4 | 0.0% | 0.0% | F:60% C:17% R22:23% | F:63% C:18% R22:18% | 10.8 |
| (<Position.CO: 'CO'>, <Position.SB: 'SB'>) | xMichax | 4 | 0.0% | 0.0% | F:73% C:9% R24:18% | F:75% C:9% R24:16% | 10.9 |
| (<Position.CO: 'CO'>, <Position.BB: 'BB'>) | xMichax | 4 | 0.0% | 0.0% | F:68% C:16% R27:16% | F:70% C:16% R27:14% | 11.6 |
| (<Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | xMichax | 4 | 0.0% | 0.0% | F:72% C:12% R26:16% | F:76% C:13% R26:11% | 10.7 |
| (<Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | xMichax | 4 | 0.0% | 0.0% | F:68% C:18% R27:14% | F:71% C:19% R27:10% | 11.1 |
| (<Position.SB: 'SB'>, <Position.BB: 'BB'>) | xMichax | 4 | 0.0% | 0.0% | F:64% C:13% R21:19% RAI:4% | F:70% C:15% R21:12% RAI:3% | 11.6 |

### 紧激进 (低VPIP/高PFR)

| 位置组合 | 玩家 | 手数 | VPIP | PFR | 先验分布 | 后验分布 | 耗时(ms) |
|---------|------|------|------|-----|---------|---------|----------|
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>) | elvq | 12 | 16.7% | 16.7% | F:62% C:16% R20:23% | F:55% C:14% R20:31% | 209.1 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>) | elvq | 12 | 16.7% | 16.7% | F:61% C:15% R20:25% | F:54% C:13% R20:33% | 211.6 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>) | elvq | 12 | 16.7% | 16.7% | F:60% C:13% R20:27% | F:49% C:11% R20:40% | 210.9 |
| (<Position.UTG: 'UTG'>, <Position.SB: 'SB'>) | elvq | 12 | 16.7% | 16.7% | F:64% C:19% R21:17% | F:56% C:17% R21:27% | 212.3 |
| (<Position.UTG: 'UTG'>, <Position.BB: 'BB'>) | elvq | 12 | 16.7% | 16.7% | F:63% C:23% R22:14% | F:55% C:20% R22:25% | 210.7 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>) | elvq | 12 | 16.7% | 16.7% | F:63% C:14% R20:24% | F:58% C:13% R20:29% | 210.4 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>) | elvq | 12 | 16.7% | 16.7% | F:61% C:13% R20:26% | F:54% C:12% R20:34% | 215.0 |
| (<Position.MP: 'MP'>, <Position.SB: 'SB'>) | elvq | 12 | 16.7% | 16.7% | F:71% C:9% R23:19% | F:63% C:8% R23:29% | 211.9 |
| (<Position.MP: 'MP'>, <Position.BB: 'BB'>) | elvq | 12 | 16.7% | 16.7% | F:64% C:20% R24:16% | F:57% C:18% R24:25% | 212.7 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | elvq | 12 | 16.7% | 16.7% | F:60% C:17% R22:23% | F:57% C:17% R22:26% | 211.9 |
| (<Position.CO: 'CO'>, <Position.SB: 'SB'>) | elvq | 12 | 16.7% | 16.7% | F:73% C:9% R24:18% | F:69% C:8% R24:23% | 212.2 |
| (<Position.CO: 'CO'>, <Position.BB: 'BB'>) | elvq | 12 | 16.7% | 16.7% | F:68% C:16% R27:16% | F:64% C:15% R27:21% | 210.3 |
| (<Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | elvq | 12 | 16.7% | 16.7% | F:72% C:12% R26:16% | F:72% C:12% R26:16% | 211.7 |
| (<Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | elvq | 12 | 16.7% | 16.7% | F:68% C:18% R27:14% | F:67% C:18% R27:15% | 208.8 |
| (<Position.SB: 'SB'>, <Position.BB: 'BB'>) | elvq | 12 | 16.7% | 16.7% | F:64% C:13% R21:19% RAI:4% | F:64% C:14% R21:18% RAI:4% | 208.5 |

### 松被动 (高VPIP/低PFR)

| 位置组合 | 玩家 | 手数 | VPIP | PFR | 先验分布 | 后验分布 | 耗时(ms) |
|---------|------|------|------|-----|---------|---------|----------|
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>) | afclockey49 | 6 | 83.3% | 0.0% | F:62% C:16% R20:23% | F:65% C:16% R20:19% | 10.1 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>) | afclockey49 | 6 | 83.3% | 0.0% | F:61% C:15% R20:25% | F:63% C:15% R20:22% | 10.4 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>) | afclockey49 | 6 | 83.3% | 0.0% | F:60% C:13% R20:27% | F:59% C:13% R20:28% | 11.0 |
| (<Position.UTG: 'UTG'>, <Position.SB: 'SB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:64% C:19% R21:17% | F:63% C:19% R21:19% | 11.0 |
| (<Position.UTG: 'UTG'>, <Position.BB: 'BB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:63% C:23% R22:14% | F:61% C:22% R22:17% | 11.5 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>) | afclockey49 | 6 | 83.3% | 0.0% | F:63% C:14% R20:24% | F:66% C:15% R20:19% | 10.8 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>) | afclockey49 | 6 | 83.3% | 0.0% | F:61% C:13% R20:26% | F:63% C:14% R20:24% | 10.6 |
| (<Position.MP: 'MP'>, <Position.SB: 'SB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:71% C:9% R23:19% | F:71% C:9% R23:20% | 10.9 |
| (<Position.MP: 'MP'>, <Position.BB: 'BB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:64% C:20% R24:16% | F:63% C:20% R24:17% | 11.4 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | afclockey49 | 6 | 83.3% | 0.0% | F:60% C:17% R22:23% | F:63% C:18% R22:18% | 10.9 |
| (<Position.CO: 'CO'>, <Position.SB: 'SB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:73% C:9% R24:18% | F:75% C:9% R24:16% | 10.9 |
| (<Position.CO: 'CO'>, <Position.BB: 'BB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:68% C:16% R27:16% | F:70% C:16% R27:14% | 11.2 |
| (<Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:72% C:12% R26:16% | F:76% C:13% R26:11% | 11.2 |
| (<Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:68% C:18% R27:14% | F:71% C:19% R27:10% | 11.0 |
| (<Position.SB: 'SB'>, <Position.BB: 'BB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:64% C:13% R21:19% RAI:4% | F:70% C:15% R21:12% RAI:3% | 11.2 |

### 松激进 (高VPIP/高PFR)

| 位置组合 | 玩家 | 手数 | VPIP | PFR | 先验分布 | 后验分布 | 耗时(ms) |
|---------|------|------|------|-----|---------|---------|----------|
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>) | Badforyou | 10 | 30.0% | 22.2% | F:62% C:16% R20:23% | F:51% C:13% R20:36% | 209.4 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>) | Badforyou | 10 | 30.0% | 22.2% | F:61% C:15% R20:25% | F:49% C:12% R20:39% | 209.2 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>) | Badforyou | 10 | 30.0% | 22.2% | F:60% C:13% R20:27% | F:44% C:10% R20:46% | 207.9 |
| (<Position.UTG: 'UTG'>, <Position.SB: 'SB'>) | Badforyou | 10 | 30.0% | 22.2% | F:64% C:19% R21:17% | F:53% C:16% R21:30% | 210.1 |
| (<Position.UTG: 'UTG'>, <Position.BB: 'BB'>) | Badforyou | 10 | 30.0% | 22.2% | F:63% C:23% R22:14% | F:52% C:19% R22:29% | 210.5 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>) | Badforyou | 10 | 30.0% | 22.2% | F:63% C:14% R20:24% | F:54% C:12% R20:34% | 208.3 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>) | Badforyou | 10 | 30.0% | 22.2% | F:61% C:13% R20:26% | F:49% C:11% R20:40% | 208.7 |
| (<Position.MP: 'MP'>, <Position.SB: 'SB'>) | Badforyou | 10 | 30.0% | 22.2% | F:71% C:9% R23:19% | F:60% C:8% R23:33% | 212.2 |
| (<Position.MP: 'MP'>, <Position.BB: 'BB'>) | Badforyou | 10 | 30.0% | 22.2% | F:64% C:20% R24:16% | F:54% C:17% R24:30% | 208.5 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | Badforyou | 10 | 30.0% | 22.2% | F:60% C:17% R22:23% | F:54% C:16% R22:31% | 211.5 |
| (<Position.CO: 'CO'>, <Position.SB: 'SB'>) | Badforyou | 10 | 30.0% | 22.2% | F:73% C:9% R24:18% | F:66% C:8% R24:26% | 208.9 |
| (<Position.CO: 'CO'>, <Position.BB: 'BB'>) | Badforyou | 10 | 30.0% | 22.2% | F:68% C:16% R27:16% | F:61% C:14% R27:25% | 209.3 |
| (<Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Badforyou | 10 | 30.0% | 22.2% | F:72% C:12% R26:16% | F:70% C:12% R26:18% | 205.5 |
| (<Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Badforyou | 10 | 30.0% | 22.2% | F:68% C:18% R27:14% | F:65% C:17% R27:18% | 209.5 |
| (<Position.SB: 'SB'>, <Position.BB: 'BB'>) | Badforyou | 10 | 30.0% | 22.2% | F:64% C:13% R21:19% RAI:4% | F:61% C:13% R21:21% RAI:4% | 208.4 |

## 数据中等 (50-300手)

### 紧被动 (低VPIP/低PFR)

| 位置组合 | 玩家 | 手数 | VPIP | PFR | 先验分布 | 后验分布 | 耗时(ms) |
|---------|------|------|------|-----|---------|---------|----------|
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>) | Turbem | 116 | 22.4% | 15.0% | F:62% C:16% R20:23% | F:57% C:14% R20:29% | 354.5 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>) | Turbem | 116 | 22.4% | 15.0% | F:61% C:15% R20:25% | F:53% C:13% R20:34% | 352.4 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>) | Turbem | 116 | 22.4% | 15.0% | F:60% C:13% R20:27% | F:50% C:11% R20:40% | 355.6 |
| (<Position.UTG: 'UTG'>, <Position.SB: 'SB'>) | Turbem | 116 | 22.4% | 15.0% | F:64% C:19% R21:17% | F:59% C:18% R21:23% | 356.5 |
| (<Position.UTG: 'UTG'>, <Position.BB: 'BB'>) | Turbem | 116 | 22.4% | 15.0% | F:63% C:23% R22:14% | F:56% C:21% R22:23% | 352.9 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>) | Turbem | 116 | 22.4% | 15.0% | F:63% C:14% R20:24% | F:57% C:13% R20:30% | 352.5 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>) | Turbem | 116 | 22.4% | 15.0% | F:61% C:13% R20:26% | F:54% C:12% R20:34% | 358.3 |
| (<Position.MP: 'MP'>, <Position.SB: 'SB'>) | Turbem | 116 | 22.4% | 15.0% | F:71% C:9% R23:19% | F:67% C:9% R23:25% | 355.1 |
| (<Position.MP: 'MP'>, <Position.BB: 'BB'>) | Turbem | 116 | 22.4% | 15.0% | F:64% C:20% R24:16% | F:58% C:18% R24:23% | 354.4 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | Turbem | 116 | 22.4% | 15.0% | F:60% C:17% R22:23% | F:57% C:17% R22:26% | 350.8 |
| (<Position.CO: 'CO'>, <Position.SB: 'SB'>) | Turbem | 116 | 22.4% | 15.0% | F:73% C:9% R24:18% | F:72% C:9% R24:20% | 355.9 |
| (<Position.CO: 'CO'>, <Position.BB: 'BB'>) | Turbem | 116 | 22.4% | 15.0% | F:68% C:16% R27:16% | F:65% C:15% R27:20% | 360.7 |
| (<Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Turbem | 116 | 22.4% | 15.0% | F:72% C:12% R26:16% | F:74% C:12% R26:14% | 355.7 |
| (<Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Turbem | 116 | 22.4% | 15.0% | F:68% C:18% R27:14% | F:68% C:18% R27:14% | 354.7 |
| (<Position.SB: 'SB'>, <Position.BB: 'BB'>) | Turbem | 116 | 22.4% | 15.0% | F:64% C:13% R21:19% RAI:4% | F:66% C:14% R21:17% RAI:3% | 351.8 |

### 紧激进 (低VPIP/高PFR)

| 位置组合 | 玩家 | 手数 | VPIP | PFR | 先验分布 | 后验分布 | 耗时(ms) |
|---------|------|------|------|-----|---------|---------|----------|
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>) | iprayforgod | 129 | 23.3% | 21.4% | F:62% C:16% R20:23% | F:53% C:13% R20:33% | 444.8 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>) | iprayforgod | 129 | 23.3% | 21.4% | F:61% C:15% R20:25% | F:53% C:13% R20:34% | 451.4 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>) | iprayforgod | 129 | 23.3% | 21.4% | F:60% C:13% R20:27% | F:46% C:10% R20:44% | 457.9 |
| (<Position.UTG: 'UTG'>, <Position.SB: 'SB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:64% C:19% R21:17% | F:56% C:17% R21:27% | 451.1 |
| (<Position.UTG: 'UTG'>, <Position.BB: 'BB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:63% C:23% R22:14% | F:54% C:20% R22:27% | 444.7 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>) | iprayforgod | 129 | 23.3% | 21.4% | F:63% C:14% R20:24% | F:58% C:13% R20:30% | 444.2 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>) | iprayforgod | 129 | 23.3% | 21.4% | F:61% C:13% R20:26% | F:51% C:11% R20:38% | 445.7 |
| (<Position.MP: 'MP'>, <Position.SB: 'SB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:71% C:9% R23:19% | F:63% C:8% R23:29% | 444.9 |
| (<Position.MP: 'MP'>, <Position.BB: 'BB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:64% C:20% R24:16% | F:56% C:17% R24:27% | 447.6 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | iprayforgod | 129 | 23.3% | 21.4% | F:60% C:17% R22:23% | F:55% C:16% R22:29% | 443.9 |
| (<Position.CO: 'CO'>, <Position.SB: 'SB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:73% C:9% R24:18% | F:69% C:8% R24:23% | 450.1 |
| (<Position.CO: 'CO'>, <Position.BB: 'BB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:68% C:16% R27:16% | F:63% C:14% R27:23% | 441.2 |
| (<Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:72% C:12% R26:16% | F:72% C:12% R26:16% | 444.5 |
| (<Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:68% C:18% R27:14% | F:66% C:18% R27:16% | 446.9 |
| (<Position.SB: 'SB'>, <Position.BB: 'BB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:64% C:13% R21:19% RAI:4% | F:63% C:13% R21:19% RAI:4% | 441.5 |

### 松被动 (高VPIP/低PFR)

| 位置组合 | 玩家 | 手数 | VPIP | PFR | 先验分布 | 后验分布 | 耗时(ms) |
|---------|------|------|------|-----|---------|---------|----------|
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>) | aafhs | 100 | 28.0% | 12.5% | F:62% C:16% R20:23% | F:59% C:15% R20:26% | 373.1 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>) | aafhs | 100 | 28.0% | 12.5% | F:61% C:15% R20:25% | F:59% C:14% R20:27% | 372.4 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>) | aafhs | 100 | 28.0% | 12.5% | F:60% C:13% R20:27% | F:56% C:12% R20:32% | 376.8 |
| (<Position.UTG: 'UTG'>, <Position.SB: 'SB'>) | aafhs | 100 | 28.0% | 12.5% | F:64% C:19% R21:17% | F:61% C:18% R21:20% | 376.4 |
| (<Position.UTG: 'UTG'>, <Position.BB: 'BB'>) | aafhs | 100 | 28.0% | 12.5% | F:63% C:23% R22:14% | F:59% C:21% R22:20% | 375.9 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>) | aafhs | 100 | 28.0% | 12.5% | F:63% C:14% R20:24% | F:63% C:14% R20:23% | 376.3 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>) | aafhs | 100 | 28.0% | 12.5% | F:61% C:13% R20:26% | F:60% C:13% R20:27% | 375.2 |
| (<Position.MP: 'MP'>, <Position.SB: 'SB'>) | aafhs | 100 | 28.0% | 12.5% | F:71% C:9% R23:19% | F:69% C:9% R23:22% | 371.4 |
| (<Position.MP: 'MP'>, <Position.BB: 'BB'>) | aafhs | 100 | 28.0% | 12.5% | F:64% C:20% R24:16% | F:61% C:19% R24:20% | 379.5 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | aafhs | 100 | 28.0% | 12.5% | F:60% C:17% R22:23% | F:61% C:18% R22:21% | 377.7 |
| (<Position.CO: 'CO'>, <Position.SB: 'SB'>) | aafhs | 100 | 28.0% | 12.5% | F:73% C:9% R24:18% | F:74% C:9% R24:17% | 373.1 |
| (<Position.CO: 'CO'>, <Position.BB: 'BB'>) | aafhs | 100 | 28.0% | 12.5% | F:68% C:16% R27:16% | F:68% C:16% R27:17% | 370.0 |
| (<Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | aafhs | 100 | 28.0% | 12.5% | F:72% C:12% R26:16% | F:75% C:13% R26:12% | 371.2 |
| (<Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | aafhs | 100 | 28.0% | 12.5% | F:68% C:18% R27:14% | F:70% C:19% R27:12% | 372.9 |
| (<Position.SB: 'SB'>, <Position.BB: 'BB'>) | aafhs | 100 | 28.0% | 12.5% | F:64% C:13% R21:19% RAI:4% | F:68% C:14% R21:14% RAI:3% | 368.9 |

### 松激进 (高VPIP/高PFR)

| 位置组合 | 玩家 | 手数 | VPIP | PFR | 先验分布 | 后验分布 | 耗时(ms) |
|---------|------|------|------|-----|---------|---------|----------|
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>) | Oatta | 108 | 38.9% | 27.0% | F:62% C:16% R20:23% | F:49% C:12% R20:39% | 800.2 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>) | Oatta | 108 | 38.9% | 27.0% | F:61% C:15% R20:25% | F:49% C:12% R20:39% | 417.7 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>) | Oatta | 108 | 38.9% | 27.0% | F:60% C:13% R20:27% | F:45% C:10% R20:46% | 416.5 |
| (<Position.UTG: 'UTG'>, <Position.SB: 'SB'>) | Oatta | 108 | 38.9% | 27.0% | F:64% C:19% R21:17% | F:53% C:16% R21:31% | 421.7 |
| (<Position.UTG: 'UTG'>, <Position.BB: 'BB'>) | Oatta | 108 | 38.9% | 27.0% | F:63% C:23% R22:14% | F:53% C:19% R22:28% | 417.0 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>) | Oatta | 108 | 38.9% | 27.0% | F:63% C:14% R20:24% | F:54% C:12% R20:34% | 418.9 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>) | Oatta | 108 | 38.9% | 27.0% | F:61% C:13% R20:26% | F:50% C:11% R20:39% | 417.6 |
| (<Position.MP: 'MP'>, <Position.SB: 'SB'>) | Oatta | 108 | 38.9% | 27.0% | F:71% C:9% R23:19% | F:59% C:8% R23:34% | 420.1 |
| (<Position.MP: 'MP'>, <Position.BB: 'BB'>) | Oatta | 108 | 38.9% | 27.0% | F:64% C:20% R24:16% | F:54% C:17% R24:29% | 422.8 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | Oatta | 108 | 38.9% | 27.0% | F:60% C:17% R22:23% | F:54% C:16% R22:30% | 822.8 |
| (<Position.CO: 'CO'>, <Position.SB: 'SB'>) | Oatta | 108 | 38.9% | 27.0% | F:73% C:9% R24:18% | F:65% C:8% R24:27% | 418.3 |
| (<Position.CO: 'CO'>, <Position.BB: 'BB'>) | Oatta | 108 | 38.9% | 27.0% | F:68% C:16% R27:16% | F:62% C:14% R27:24% | 419.7 |
| (<Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Oatta | 108 | 38.9% | 27.0% | F:72% C:12% R26:16% | F:69% C:12% R26:19% | 416.2 |
| (<Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Oatta | 108 | 38.9% | 27.0% | F:68% C:18% R27:14% | F:65% C:18% R27:17% | 413.6 |
| (<Position.SB: 'SB'>, <Position.BB: 'BB'>) | Oatta | 108 | 38.9% | 27.0% | F:64% C:13% R21:19% RAI:4% | F:62% C:13% R21:21% RAI:4% | 421.8 |

## 数据充足 (>300手)

### 紧被动 (低VPIP/低PFR)

| 位置组合 | 玩家 | 手数 | VPIP | PFR | 先验分布 | 后验分布 | 耗时(ms) |
|---------|------|------|------|-----|---------|---------|----------|
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>) | oleh2222 | 802 | 12.0% | 8.2% | F:62% C:16% R20:23% | F:65% C:16% R20:19% | 424.8 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>) | oleh2222 | 802 | 12.0% | 8.2% | F:61% C:15% R20:25% | F:67% C:16% R20:17% | 424.7 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>) | oleh2222 | 802 | 12.0% | 8.2% | F:60% C:13% R20:27% | F:63% C:14% R20:23% | 435.1 |
| (<Position.UTG: 'UTG'>, <Position.SB: 'SB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:64% C:19% R21:17% | F:64% C:19% R21:17% | 424.1 |
| (<Position.UTG: 'UTG'>, <Position.BB: 'BB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:63% C:23% R22:14% | F:63% C:23% R22:14% | 425.0 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>) | oleh2222 | 802 | 12.0% | 8.2% | F:63% C:14% R20:24% | F:70% C:15% R20:15% | 430.2 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>) | oleh2222 | 802 | 12.0% | 8.2% | F:61% C:13% R20:26% | F:66% C:14% R20:20% | 429.0 |
| (<Position.MP: 'MP'>, <Position.SB: 'SB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:71% C:9% R23:19% | F:73% C:9% R23:18% | 429.0 |
| (<Position.MP: 'MP'>, <Position.BB: 'BB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:64% C:20% R24:16% | F:65% C:20% R24:14% | 433.7 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | oleh2222 | 802 | 12.0% | 8.2% | F:60% C:17% R22:23% | F:66% C:19% R22:15% | 427.6 |
| (<Position.CO: 'CO'>, <Position.SB: 'SB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:73% C:9% R24:18% | F:77% C:9% R24:14% | 426.2 |
| (<Position.CO: 'CO'>, <Position.BB: 'BB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:68% C:16% R27:16% | F:72% C:16% R27:12% | 427.0 |
| (<Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:72% C:12% R26:16% | F:77% C:13% R26:10% | 426.7 |
| (<Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:68% C:18% R27:14% | F:72% C:19% R27:8% | 426.2 |
| (<Position.SB: 'SB'>, <Position.BB: 'BB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:64% C:13% R21:19% RAI:4% | F:72% C:15% R21:10% RAI:2% | 426.1 |

### 紧激进 (低VPIP/高PFR)

| 位置组合 | 玩家 | 手数 | VPIP | PFR | 先验分布 | 后验分布 | 耗时(ms) |
|---------|------|------|------|-----|---------|---------|----------|
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>) | Noris22 | 1124 | 24.6% | 16.1% | F:62% C:16% R20:23% | F:62% C:16% R20:23% | 398.1 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>) | Noris22 | 1124 | 24.6% | 16.1% | F:61% C:15% R20:25% | F:61% C:15% R20:24% | 400.9 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>) | Noris22 | 1124 | 24.6% | 16.1% | F:60% C:13% R20:27% | F:59% C:13% R20:28% | 402.8 |
| (<Position.UTG: 'UTG'>, <Position.SB: 'SB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:64% C:19% R21:17% | F:63% C:19% R21:18% | 396.3 |
| (<Position.UTG: 'UTG'>, <Position.BB: 'BB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:63% C:23% R22:14% | F:62% C:22% R22:16% | 407.2 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>) | Noris22 | 1124 | 24.6% | 16.1% | F:63% C:14% R20:24% | F:65% C:14% R20:21% | 395.0 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>) | Noris22 | 1124 | 24.6% | 16.1% | F:61% C:13% R20:26% | F:62% C:14% R20:24% | 397.8 |
| (<Position.MP: 'MP'>, <Position.SB: 'SB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:71% C:9% R23:19% | F:72% C:9% R23:19% | 399.6 |
| (<Position.MP: 'MP'>, <Position.BB: 'BB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:64% C:20% R24:16% | F:64% C:20% R24:16% | 401.9 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | Noris22 | 1124 | 24.6% | 16.1% | F:60% C:17% R22:23% | F:63% C:18% R22:18% | 394.0 |
| (<Position.CO: 'CO'>, <Position.SB: 'SB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:73% C:9% R24:18% | F:76% C:9% R24:15% | 394.2 |
| (<Position.CO: 'CO'>, <Position.BB: 'BB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:68% C:16% R27:16% | F:70% C:16% R27:14% | 399.4 |
| (<Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:72% C:12% R26:16% | F:77% C:13% R26:11% | 391.0 |
| (<Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:68% C:18% R27:14% | F:71% C:19% R27:10% | 822.4 |
| (<Position.SB: 'SB'>, <Position.BB: 'BB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:64% C:13% R21:19% RAI:4% | F:71% C:15% R21:12% RAI:2% | 399.0 |

### 松被动 (高VPIP/低PFR)

| 位置组合 | 玩家 | 手数 | VPIP | PFR | 先验分布 | 后验分布 | 耗时(ms) |
|---------|------|------|------|-----|---------|---------|----------|
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>) | Dorororoo | 535 | 32.7% | 13.2% | F:62% C:16% R20:23% | F:59% C:15% R20:26% | 348.9 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>) | Dorororoo | 535 | 32.7% | 13.2% | F:61% C:15% R20:25% | F:61% C:15% R20:25% | 356.4 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>) | Dorororoo | 535 | 32.7% | 13.2% | F:60% C:13% R20:27% | F:58% C:13% R20:29% | 356.4 |
| (<Position.UTG: 'UTG'>, <Position.SB: 'SB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:64% C:19% R21:17% | F:62% C:19% R21:20% | 347.0 |
| (<Position.UTG: 'UTG'>, <Position.BB: 'BB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:63% C:23% R22:14% | F:61% C:22% R22:16% | 784.6 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>) | Dorororoo | 535 | 32.7% | 13.2% | F:63% C:14% R20:24% | F:64% C:14% R20:22% | 354.2 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>) | Dorororoo | 535 | 32.7% | 13.2% | F:61% C:13% R20:26% | F:62% C:14% R20:25% | 348.3 |
| (<Position.MP: 'MP'>, <Position.SB: 'SB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:71% C:9% R23:19% | F:70% C:9% R23:21% | 354.2 |
| (<Position.MP: 'MP'>, <Position.BB: 'BB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:64% C:20% R24:16% | F:64% C:20% R24:16% | 355.4 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | Dorororoo | 535 | 32.7% | 13.2% | F:60% C:17% R22:23% | F:63% C:18% R22:19% | 351.1 |
| (<Position.CO: 'CO'>, <Position.SB: 'SB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:73% C:9% R24:18% | F:74% C:9% R24:17% | 355.6 |
| (<Position.CO: 'CO'>, <Position.BB: 'BB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:68% C:16% R27:16% | F:70% C:16% R27:14% | 351.7 |
| (<Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:72% C:12% R26:16% | F:75% C:13% R26:12% | 349.5 |
| (<Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:68% C:18% R27:14% | F:71% C:19% R27:10% | 352.8 |
| (<Position.SB: 'SB'>, <Position.BB: 'BB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:64% C:13% R21:19% RAI:4% | F:71% C:15% R21:12% RAI:2% | 351.6 |

### 松激进 (高VPIP/高PFR)

| 位置组合 | 玩家 | 手数 | VPIP | PFR | 先验分布 | 后验分布 | 耗时(ms) |
|---------|------|------|------|-----|---------|---------|----------|
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>) | Deteuler | 638 | 27.0% | 21.4% | F:62% C:16% R20:23% | F:57% C:14% R20:29% | 466.6 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>) | Deteuler | 638 | 27.0% | 21.4% | F:61% C:15% R20:25% | F:54% C:13% R20:33% | 467.8 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>) | Deteuler | 638 | 27.0% | 21.4% | F:60% C:13% R20:27% | F:50% C:11% R20:39% | 472.1 |
| (<Position.UTG: 'UTG'>, <Position.SB: 'SB'>) | Deteuler | 638 | 27.0% | 21.4% | F:64% C:19% R21:17% | F:57% C:17% R21:26% | 468.1 |
| (<Position.UTG: 'UTG'>, <Position.BB: 'BB'>) | Deteuler | 638 | 27.0% | 21.4% | F:63% C:23% R22:14% | F:59% C:21% R22:20% | 467.4 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>) | Deteuler | 638 | 27.0% | 21.4% | F:63% C:14% R20:24% | F:58% C:13% R20:29% | 461.2 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>) | Deteuler | 638 | 27.0% | 21.4% | F:61% C:13% R20:26% | F:55% C:12% R20:33% | 472.0 |
| (<Position.MP: 'MP'>, <Position.SB: 'SB'>) | Deteuler | 638 | 27.0% | 21.4% | F:71% C:9% R23:19% | F:64% C:8% R23:28% | 472.4 |
| (<Position.MP: 'MP'>, <Position.BB: 'BB'>) | Deteuler | 638 | 27.0% | 21.4% | F:64% C:20% R24:16% | F:61% C:19% R24:20% | 469.8 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | Deteuler | 638 | 27.0% | 21.4% | F:60% C:17% R22:23% | F:58% C:17% R22:26% | 462.6 |
| (<Position.CO: 'CO'>, <Position.SB: 'SB'>) | Deteuler | 638 | 27.0% | 21.4% | F:73% C:9% R24:18% | F:69% C:8% R24:22% | 470.8 |
| (<Position.CO: 'CO'>, <Position.BB: 'BB'>) | Deteuler | 638 | 27.0% | 21.4% | F:68% C:16% R27:16% | F:67% C:15% R27:17% | 465.2 |
| (<Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Deteuler | 638 | 27.0% | 21.4% | F:72% C:12% R26:16% | F:72% C:12% R26:16% | 457.0 |
| (<Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Deteuler | 638 | 27.0% | 21.4% | F:68% C:18% R27:14% | F:69% C:19% R27:12% | 466.6 |
| (<Position.SB: 'SB'>, <Position.BB: 'BB'>) | Deteuler | 638 | 27.0% | 21.4% | F:64% C:13% R21:19% RAI:4% | F:68% C:14% R21:15% RAI:3% | 463.5 |

